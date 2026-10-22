import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/models/nearby_place.dart';
import 'package:mobile/services/nearby_places_service.dart';

Map<String, dynamic> _placePayload(String id, double lat, double lon) {
  return <String, dynamic>{
    'id': id,
    'name': 'Place $id',
    'category': 'hospital',
    'latitude': lat,
    'longitude': lon,
    'distance_m': 500,
    'address': null,
  };
}

http.Response _placesResponse(List<Map<String, dynamic>> places) {
  return http.Response(
    jsonEncode(<String, dynamic>{'places': places}),
    200,
  );
}

void main() {
  test('findNearbyForAnchors queries both endpoints and tags anchors', () async {
    final List<Uri> requested = <Uri>[];
    final MockClient client = MockClient((http.Request request) async {
      requested.add(request.url);
      final double lat = double.parse(request.url.queryParameters['lat']!);
      if (lat < 18.53) {
        return _placesResponse(<Map<String, dynamic>>[
          _placePayload('node/1', 18.521, 73.851),
          _placePayload('node/2', 18.511, 73.841),
        ]);
      }
      return _placesResponse(<Map<String, dynamic>>[
        _placePayload('node/2', 18.511, 73.841),
        _placePayload('node/3', 18.541, 73.861),
      ]);
    });

    final NearbyPlacesService service = NearbyPlacesService(
      client: client,
      apiBaseUrl: 'http://mock-api',
    );

    final List<NearbyPlace> places = await service.findNearbyForAnchors(
      category: NearbyCategory.hospital,
      start: const LatLng(18.52, 73.85),
      end: const LatLng(18.54, 73.86),
    );

    expect(requested, hasLength(2));
    expect(places, hasLength(3));
    expect(
      places.where((NearbyPlace place) => place.anchor == NearbyAnchor.routeStart),
      hasLength(2),
    );
    expect(
      places.where((NearbyPlace place) => place.anchor == NearbyAnchor.routeEnd),
      hasLength(1),
    );
    expect(
      places.where((NearbyPlace place) => place.id == 'node/2').first.anchor,
      NearbyAnchor.routeStart,
    );
  });

  test(
    'findNearbyForAnchors collapses to one request for identical anchors',
    () async {
      final List<Uri> requested = <Uri>[];
      final MockClient client = MockClient((http.Request request) async {
        requested.add(request.url);
        return _placesResponse(<Map<String, dynamic>>[
          _placePayload('node/9', 18.52, 73.85),
        ]);
      });

      final NearbyPlacesService service = NearbyPlacesService(
        client: client,
        apiBaseUrl: 'http://mock-api',
      );

      final List<NearbyPlace> places = await service.findNearbyForAnchors(
        category: NearbyCategory.police,
        start: const LatLng(18.52, 73.85),
        end: const LatLng(18.52, 73.85001),
      );

      expect(requested, hasLength(1));
      expect(places, hasLength(1));
      expect(places.first.anchor, NearbyAnchor.routeStart);
    },
  );
}
