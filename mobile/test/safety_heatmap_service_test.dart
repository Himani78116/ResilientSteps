import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/models/safety_zone.dart';
import 'package:mobile/services/safety_heatmap_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('SafetyHeatmapService limits cached zones to 1000 items', () async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    
    // 1. Create a large initial list of cached zones (950 items)
    final List<Map<String, dynamic>> initialZones = List.generate(950, (index) {
      return {
        'id': 'zone_$index',
        'lat': 18.5204 + (index * 0.0001),
        'lon': 73.8567 + (index * 0.0001),
        'score': 80.0,
        'radius_meters': 120.0,
        'classification': 'SAFE',
        'polygon_points': [
          [73.8567, 18.5204],
          [73.8568, 18.5204],
          [73.8568, 18.5205],
          [73.8567, 18.5204],
        ],
      };
    });
    
    await prefs.setString('walksafe_safety_zones_cache', jsonEncode(initialZones));

    // 2. Mock client returning 100 fresh zones (20 overlapping, 80 new ones).
    // Total distinct zones will be 950 + 80 = 1030.
    // The merged count must be capped at 1000.
    final List<Map<String, dynamic>> freshFeatures = List.generate(100, (index) {
      final int idNum = index < 20 ? index : 950 + (index - 20); // 0-19 overlap, 950-1029 new
      return {
        'type': 'Feature',
        'geometry': {
          'type': 'Polygon',
          'coordinates': [
            [
              [73.8567, 18.5204],
              [73.8568, 18.5204],
              [73.8568, 18.5205],
              [73.8567, 18.5204],
            ]
          ]
        },
        'properties': {
          'zone_id': 'zone_$idNum',
          'risk_score': 0.2,
          'risk_level': 'SAFE',
        }
      };
    });

    final mockClient = MockClient((request) async {
      return http.Response(
        jsonEncode({'features': freshFeatures}),
        200,
      );
    });

    final service = SafetyHeatmapService(client: mockClient, apiBaseUrl: 'http://mock-api');
    
    // Call loadSafetyZones to trigger merge and cache
    await service.loadSafetyZones(refresh: true);

    // 3. Verify that the cached zones count is capped at 1000
    final String? cachedRaw = prefs.getString('walksafe_safety_zones_cache');
    expect(cachedRaw, isNotNull);
    final List<dynamic> cachedList = jsonDecode(cachedRaw!) as List<dynamic>;
    expect(cachedList.length, equals(1000));

    // Verify that the newest zones (like zone_1029) are in the cache
    final List<String> cachedIds = cachedList.map((z) => z['id'].toString()).toList();
    expect(cachedIds.contains('zone_1029'), isTrue);
    // And older zones (e.g. zone_20) have been evicted to maintain 1000 items
    expect(cachedIds.contains('zone_20'), isFalse);
  });
}
