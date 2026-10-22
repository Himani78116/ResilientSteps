import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../config/app_config.dart';
import '../models/nearby_place.dart';

class NearbyPlacesService {
  NearbyPlacesService({http.Client? client, String? apiBaseUrl})
    : _client = client ?? http.Client(),
      _apiBaseUrl = apiBaseUrl ?? AppConfig.apiBaseUrl;

  final http.Client _client;
  final String _apiBaseUrl;

  Future<List<NearbyPlace>> findNearby({
    required double latitude,
    required double longitude,
    required NearbyCategory category,
    int radiusMeters = 3000,
  }) async {
    final Uri uri = Uri.parse('$_apiBaseUrl/nearby-places').replace(
      queryParameters: <String, String>{
        'lat': latitude.toString(),
        'lon': longitude.toString(),
        'category': category.code,
        'radius_m': radiusMeters.toString(),
      },
    );
    late final http.Response response;
    try {
      response = await _client.get(uri).timeout(const Duration(seconds: 15));
    } catch (error) {
      debugPrint('NearbyPlacesService: request failed for $uri: $error');
      throw Exception(
        'Unable to contact the nearby-places server. Check API_BASE_URL '
        'and make sure the backend is running.',
      );
    }
    if (response.statusCode != 200) {
      debugPrint(
        'NearbyPlacesService: HTTP ${response.statusCode} from $uri: '
        '${response.body}',
      );
      String detail = 'Nearby places are unavailable right now.';
      try {
        final dynamic body = jsonDecode(response.body);
        if (body is Map && body['detail'] is String) {
          detail = body['detail'] as String;
        }
      } on FormatException {
        // Keep the user-facing fallback when the server response is not JSON.
      }
      throw Exception(detail);
    }
    final dynamic decoded = jsonDecode(response.body);
    if (decoded is! Map || decoded['places'] is! List) {
      throw Exception('Nearby places returned an invalid response.');
    }
    return (decoded['places'] as List)
        .whereType<Map>()
        .map(
          (Map item) => NearbyPlace.fromJson(
            item.map((dynamic key, dynamic value) => MapEntry('$key', value)),
          ),
        )
        .where(
          (NearbyPlace place) => place.latitude != 0 && place.longitude != 0,
        )
        .toList(growable: false);
  }

  /// Searches around two anchors of a route. When only one anchor is given
  /// (or both collapse to the same spot) a single request keeps behaviour
  /// identical to [findNearby].
  Future<List<NearbyPlace>> findNearbyForAnchors({
    required NearbyCategory category,
    LatLng? start,
    LatLng? end,
    int radiusMeters = 3000,
  }) async {
    final LatLng? singleAnchor;
    if (start == null || end == null) {
      singleAnchor = start ?? end;
    } else if (_samePoint(start, end)) {
      singleAnchor = start;
    } else {
      singleAnchor = null;
    }

    if (singleAnchor != null) {
      final NearbyAnchor anchorType = start == null
          ? NearbyAnchor.routeEnd
          : NearbyAnchor.routeStart;
      final List<NearbyPlace> places = await findNearby(
        latitude: singleAnchor.latitude,
        longitude: singleAnchor.longitude,
        category: category,
        radiusMeters: radiusMeters,
      );
      return places
          .map((NearbyPlace place) => place.withAnchor(anchorType))
          .toList(growable: false);
    }

    final List<List<NearbyPlace>> results =
        await Future.wait(<Future<List<NearbyPlace>>>[
      findNearby(
        latitude: start!.latitude,
        longitude: start.longitude,
        category: category,
        radiusMeters: radiusMeters,
      ),
      findNearby(
        latitude: end!.latitude,
        longitude: end.longitude,
        category: category,
        radiusMeters: radiusMeters,
      ),
    ]);
    return _mergeAnchored(results[0].map(_withStartAnchor), results[1].map(_withEndAnchor));
  }

  static bool _samePoint(LatLng? a, LatLng? b) {
    if (a == null || b == null) {
      return false;
    }
    const double tolerance = 1e-4;
    return (a.latitude - b.latitude).abs() < tolerance &&
        (a.longitude - b.longitude).abs() < tolerance;
  }

  static NearbyPlace _withStartAnchor(NearbyPlace place) =>
      place.withAnchor(NearbyAnchor.routeStart);

  static NearbyPlace _withEndAnchor(NearbyPlace place) =>
      place.withAnchor(NearbyAnchor.routeEnd);

  static List<NearbyPlace> _mergeAnchored(
    Iterable<NearbyPlace> startPlaces,
    Iterable<NearbyPlace> endPlaces,
  ) {
    final Map<String, NearbyPlace> merged = <String, NearbyPlace>{};
    for (final NearbyPlace place in startPlaces) {
      merged[place.id] = place;
    }
    for (final NearbyPlace place in endPlaces) {
      merged.putIfAbsent(place.id, () => place);
    }
    return merged.values.toList(growable: false);
  }
}
