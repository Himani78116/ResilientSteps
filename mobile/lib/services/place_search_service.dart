import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/place_suggestion.dart';

class PlaceSearchService {
  PlaceSearchService({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  static const Duration _timeout = Duration(seconds: 10);
  static const String _viewBox = '73.777,18.607,73.935,18.438';

  Future<List<PlaceSuggestion>> searchDestinations(String query) async {
    final String normalized = query.trim();
    if (normalized.length < 2) {
      return <PlaceSuggestion>[];
    }

    final Uri uri = Uri.parse(
      'https://nominatim.openstreetmap.org/search',
    ).replace(
      queryParameters: <String, String>{
        'q': normalized,
        'format': 'jsonv2',
        'limit': '8',
        'addressdetails': '1',
        'countrycodes': 'in',
        'viewbox': _viewBox,
        'bounded': '1',
      },
    );

    final http.Response response = await _client
        .get(
          uri,
          headers: const <String, String>{
            'User-Agent': 'WalkSafeMobile/1.0',
            'Accept-Language': 'en',
          },
        )
        .timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Search is unavailable right now.');
    }

    final dynamic decoded = jsonDecode(response.body);
    if (decoded is! List) {
      return <PlaceSuggestion>[];
    }

    return decoded
        .whereType<Map>()
        .map(
          (Map item) => PlaceSuggestion.fromJson(
            item.map(
              (dynamic key, dynamic value) =>
                  MapEntry(key.toString(), value),
            ),
          ),
        )
        .where(
          (PlaceSuggestion suggestion) =>
              suggestion.latitude != 0 || suggestion.longitude != 0,
        )
        .toList(growable: false);
  }
}
