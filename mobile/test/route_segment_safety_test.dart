import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/models/scored_route.dart';
import 'package:mobile/services/routing_service.dart';

Map<String, dynamic> _segment({
  required double startLat,
  required double startLon,
  required double endLat,
  required double endLon,
  double? shadeScore,
  double? heatPenalty,
  double? comfortScore,
}) {
  return <String, dynamic>{
    'start': <String, double>{'lat': startLat, 'lon': startLon},
    'end': <String, double>{'lat': endLat, 'lon': endLon},
    'length_m': 100.0,
    'matched': true,
    'base_safety_score': 80.0,
    'safety_score': 80.0,
    'shade_score': shadeScore,
    'heat_penalty': heatPenalty,
    'comfort_score': comfortScore,
    'road_segment_id': 101,
    'road_type': 'residential',
    'lighting': true,
    'match_distance_m': 1.0,
    'incident_count': 0,
    'incident_weight': 0.0,
    'incident_penalty': 0.0,
    'incident_categories': <String>[],
    'zone': null,
  };
}

void main() {
  test('RoutingService parses segment and route comfort fields', () async {
    final MockClient client = MockClient((http.Request request) async {
      return http.Response(
        jsonEncode(<String, dynamic>{
          'coordinates': <List<double>>[
            <double>[18.52, 73.85],
            <double>[18.53, 73.86],
          ],
          'safety_score': 80.0,
          'comfort_score': 74.0,
          'comfort_level': 'comfortable',
          'distance_km': 1.5,
          'duration_minutes': 12.0,
          'segments': <Map<String, dynamic>>[
            _segment(
              startLat: 18.52,
              startLon: 73.85,
              endLat: 18.53,
              endLon: 73.86,
              shadeScore: 60.0,
              heatPenalty: 5.0,
              comfortScore: 74.0,
            ),
          ],
        }),
        200,
      );
    });

    final RoutingService service = RoutingService(
      client: client,
      apiBaseUrl: 'http://mock-api',
    );
    final ScoredRoute? route = await service.getSafestRoute(
      const LatLng(18.52, 73.85),
      const LatLng(18.53, 73.86),
    );

    expect(route, isNotNull);
    expect(route!.comfortScore, equals(74.0));
    expect(route.comfortLevel, equals('comfortable'));
    expect(route.segments, hasLength(1));
    expect(route.segments.first.shadeScore, equals(60.0));
    expect(route.segments.first.heatPenalty, equals(5.0));
    expect(route.segments.first.comfortScore, equals(74.0));
    expect(route.comfortSummary, contains('74% comfortable'));
  });

  test('nullable comfort fields degrade safely to null', () async {
    final MockClient client = MockClient((http.Request request) async {
      return http.Response(
        jsonEncode(<String, dynamic>{
          'coordinates': <List<double>>[
            <double>[18.52, 73.85],
            <double>[18.53, 73.86],
          ],
          'safety_score': 80.0,
          'segments': <Map<String, dynamic>>[
            _segment(
              startLat: 18.52,
              startLon: 73.85,
              endLat: 18.53,
              endLon: 73.86,
            ),
          ],
        }),
        200,
      );
    });

    final RoutingService service = RoutingService(
      client: client,
      apiBaseUrl: 'http://mock-api',
    );
    final ScoredRoute? route = await service.getSafestRoute(
      const LatLng(18.52, 73.85),
      const LatLng(18.53, 73.86),
    );

    expect(route, isNotNull);
    expect(route!.comfortScore, isNull);
    expect(route.comfortLevel, isNull);
    expect(route.comfortSummary, isNull);
    expect(route.segments.first.shadeScore, isNull);
    expect(route.segments.first.heatPenalty, isNull);
    expect(route.segments.first.comfortScore, isNull);
  });
}
