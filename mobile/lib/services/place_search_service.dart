import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/place_suggestion.dart';

class PlaceSearchService {
  PlaceSearchService({http.Client? client}) : _client = client ?? http.Client();

  http.Client _client;

  static const Duration _timeout = Duration(seconds: 10);
  static const String _viewBox = '73.777,18.607,73.935,18.438';

  // Nominatim throttles clients above 1 request/second with HTTP 403/429,
  // which used to surface as "school search stops working on the 2nd try".
  // Keep a global rate gate and a small result cache so repeat/typed-again
  // queries never hit the service harder than once per second.
  static const Duration _minRequestInterval = Duration(
    milliseconds: 1100,
  );
  static const int _maxCacheEntries = 24;

  DateTime? _lastRequestAt;
  Future<void>? _rateGateWaiter;
  final Map<String, List<PlaceSuggestion>> _recentResults = <String,
      List<PlaceSuggestion>>{};

  Future<List<PlaceSuggestion>> searchDestinations(String query) async {
    final String normalized = query.trim();
    if (normalized.length < 2) {
      return <PlaceSuggestion>[];
    }

    final String cacheKey = normalized.toLowerCase();
    final List<PlaceSuggestion>? cached = _recentResults[cacheKey];
    if (cached != null) {
      return cached;
    }

    // Fail fast for consecutive searches instead of throwing a throttle
    // error at the caller right away.
    final http.Response response = await _throttledGet(
      _buildUri(normalized),
      retriesLeft: 1,
    );

    if (response.statusCode != 200) {
      _dropBrokenClient();
      throw Exception('Search is unavailable right now.');
    }

    final dynamic decoded = jsonDecode(response.body);
    if (decoded is! List) {
      return <PlaceSuggestion>[];
    }

    final List<PlaceSuggestion> results = decoded
        .whereType<Map>()
        .map(
          (Map item) => PlaceSuggestion.fromJson(
            item.map(
              (dynamic key, dynamic value) => MapEntry(key.toString(), value),
            ),
          ),
        )
        .where(
          (PlaceSuggestion suggestion) =>
              suggestion.latitude != 0 || suggestion.longitude != 0,
        )
        .toList(growable: false);
    _storeResults(cacheKey, results);
    return results;
  }

  Uri _buildUri(String query) {
    return Uri.parse(
      'https://nominatim.openstreetmap.org/search',
    ).replace(
      queryParameters: <String, String>{
        'q': query,
        'format': 'jsonv2',
        'limit': '8',
        'addressdetails': '1',
        'countrycodes': 'in',
        'viewbox': _viewBox,
        'bounded': '1',
      },
    );
  }

  Uri _buildReverseUri(double lat, double lon) {
    return Uri.parse(
      'https://nominatim.openstreetmap.org/reverse',
    ).replace(
      queryParameters: <String, String>{
        'lat': lat.toString(),
        'lon': lon.toString(),
        'format': 'jsonv2',
        'zoom': '17',
        'addressdetails': '1',
        'countrycodes': 'in',
      },
    );
  }

  /// Resolves a point (e.g. the live GPS fix) into a human place name so the
  /// app can ask ``are you at <place>?`` like Google Maps' origin step. Shares
  /// the Nominatim rate gate with forward search; returns null on any
  /// failure so callers can fall back to "Current location".
  Future<PlaceSuggestion?> reverseGeocode(double lat, double lon) async {
    // ~11 m buckets keep repeat fixes at the same street block cached.
    final String cacheKey =
        'reverse:${lat.toStringAsFixed(4)},${lon.toStringAsFixed(4)}';
    final List<PlaceSuggestion>? cached = _recentResults[cacheKey];
    if (cached != null && cached.isNotEmpty) {
      return cached.first;
    }

    final http.Response response = await _throttledGet(
      _buildReverseUri(lat, lon),
      retriesLeft: 1,
    );

    if (response.statusCode != 200) {
      _dropBrokenClient();
      return null;
    }

    final dynamic decoded = jsonDecode(response.body);
    if (decoded is! Map) {
      return null;
    }

    final PlaceSuggestion suggestion = PlaceSuggestion.fromJson(
      decoded.map(
        (dynamic key, dynamic value) => MapEntry(key.toString(), value),
      ),
    );
    if (suggestion.title.trim().isEmpty ||
        (suggestion.latitude == 0 && suggestion.longitude == 0)) {
      return null;
    }

    _storeResults(cacheKey, <PlaceSuggestion>[suggestion]);
    return suggestion;
  }

  Future<http.Response> _throttledGet(Uri uri, {required int retriesLeft}) async {
    final Future<void>? waiter = _rateGateWaiter;
    if (waiter != null) {
      await waiter;
    }

    final Duration sinceLast = DateTime.now().difference(
      _lastRequestAt ?? DateTime(0),
    );
    final Duration remaining = _minRequestInterval - sinceLast;
    if (!remaining.isNegative) {
      final Future<void> wait = Future<void>.delayed(remaining);
      _rateGateWaiter = wait;
      await wait;
      _rateGateWaiter = null;
    }

    _lastRequestAt = DateTime.now();
    final http.Response response;
    try {
      response = await _client
          .get(
            uri,
            headers: const <String, String>{
              'User-Agent': 'ResilientStepsMobile/1.0',
              'Accept-Language': 'en',
            },
          )
          .timeout(_timeout);
    } catch (e) {
      _dropBrokenClient();
      rethrow;
    }

    // 403/429 are Nominatim rate-limit responses; wait one full second
    // (its documented policy) and retry once before failing.
    final bool throttled =
        response.statusCode == 403 ||
        response.statusCode == 429 ||
        response.statusCode >= 500;
    if (throttled && retriesLeft > 0) {
      _lastRequestAt = null;
      final Future<void> coolDown = Future<void>.delayed(
        const Duration(milliseconds: 1600),
      );
      _rateGateWaiter = coolDown;
      await coolDown;
      _rateGateWaiter = null;
      return _throttledGet(uri, retriesLeft: retriesLeft - 1);
    }

    return response;
  }

  void _dropBrokenClient() {
    try {
      _client.close();
    } catch (_) {}
    _client = http.Client();
  }

  void _storeResults(String key, List<PlaceSuggestion> results) {
    if (results.isEmpty) {
      return;
    }
    _recentResults[key] = results;
    while (_recentResults.length > _maxCacheEntries) {
      _recentResults.remove(_recentResults.keys.first);
    }
  }
}
