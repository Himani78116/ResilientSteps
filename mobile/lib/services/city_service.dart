import 'dart:async';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import 'api_utils.dart' as api_utils;

class CityService {
  CityService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? _envBaseUrl;

  static const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');
  static const Duration _timeout = Duration(seconds: 5);

  final http.Client _client;
  final String _baseUrl;

  Future<LatLng?> fetchCityCenter() async {
    if (_baseUrl.isEmpty) return null;

    try {
      final Uri uri = Uri.parse('$_baseUrl/city');
      final http.Response response = await _client.get(uri).timeout(_timeout);

      if (response.statusCode == 200) {
        final Map<String, dynamic>? data = api_utils.tryParseJsonMap(response.body);
        if (data != null && data.containsKey('center')) {
          final Map<String, dynamic>? center = api_utils.coerceMap(data['center']);
          if (center != null) {
            final double? lat = api_utils.asDouble(center['lat']);
            final double? lon = api_utils.asDouble(center['lon']);
            if (lat != null && lon != null) {
              return LatLng(lat, lon);
            }
          }
        }
      }
    } catch (_) {}

    return null;
  }
}
