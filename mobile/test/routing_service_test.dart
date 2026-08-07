import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/models/scored_route.dart';
import 'package:mobile/services/routing_service.dart';

void main() {
  test('RoutingService getSafestRoute uses /route-safe first and avoids multi-call', () async {
    final List<String> requestedPaths = [];

    final mockClient = MockClient((request) async {
      requestedPaths.add(request.url.path);
      if (request.url.path == '/route-safe') {
        return http.Response(
          jsonEncode({
            'coordinates': [
              [18.52, 73.85],
              [18.53, 73.86]
            ],
            'safety_score': 85.0,
            'distance_km': 1.5,
            'duration_minutes': 12.0,
            'segments': [],
          }),
          200,
        );
      }
      return http.Response('Not Found', 404);
    });

    final service = RoutingService(client: mockClient, apiBaseUrl: 'http://mock-api');
    final ScoredRoute? route = await service.getSafestRoute(
      const LatLng(18.52, 73.85),
      const LatLng(18.53, 73.86),
    );

    expect(route, isNotNull);
    expect(route!.averageSafetyScore, equals(85.0));
    expect(route.points.length, equals(2));
    expect(requestedPaths, equals(['/route-safe']));
  });

  test('RoutingService getSafestRoute falls back to separate endpoints if /route-safe fails', () async {
    final List<String> requestedPaths = [];

    final mockClient = MockClient((request) async {
      requestedPaths.add(request.url.path);
      if (request.url.path == '/route-safe') {
        return http.Response('Internal Server Error', 500);
      }
      if (request.url.path == '/route') {
        return http.Response(
          jsonEncode({
            'safest': [
              {'lat': 18.52, 'lon': 73.85},
              {'lat': 18.53, 'lon': 73.86}
            ]
          }),
          200,
        );
      }
      if (request.url.path == '/route/risk') {
        return http.Response(
          jsonEncode({
            'safety_score': 75.0,
            'distance_km': 1.5,
            'duration_minutes': 12.0,
            'segments': [],
          }),
          200,
        );
      }
      return http.Response('Not Found', 404);
    });

    final service = RoutingService(client: mockClient, apiBaseUrl: 'http://mock-api');
    final ScoredRoute? route = await service.getSafestRoute(
      const LatLng(18.52, 73.85),
      const LatLng(18.53, 73.86),
    );

    expect(route, isNotNull);
    expect(route!.averageSafetyScore, equals(75.0));
    expect(route.points.length, equals(2));
    expect(requestedPaths, containsAll(['/route-safe', '/route', '/route/risk']));
  });
}
