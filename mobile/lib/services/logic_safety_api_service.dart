import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';

import '../models/logic_safety_score.dart';

class LogicSafetyApiService {
  LogicSafetyApiService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? _envBaseUrl;

  static const String _envBaseUrl = String.fromEnvironment('API_BASE_URL');

  final http.Client _client;
  final String _baseUrl;

  String get baseUrl => _baseUrl;

  Future<LogicSafetyScore> getNearestSafetyScore(LatLng point) async {
    final Uri uri = Uri.parse('$_baseUrl/safety-score').replace(
      queryParameters: <String, String>{
        'lat': point.latitude.toString(),
        'lon': point.longitude.toString(),
      },
    );

    final http.Response response = await _client.get(uri);
    if (response.statusCode != 200) {
      throw Exception(
        'Logic API request failed with status ${response.statusCode}.',
      );
    }

    final Map<String, dynamic> payload =
        jsonDecode(response.body) as Map<String, dynamic>;
    return LogicSafetyScore.fromJson(payload);
  }
}
