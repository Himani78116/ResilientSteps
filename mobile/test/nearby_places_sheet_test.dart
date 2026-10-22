import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/models/nearby_place.dart';
import 'package:mobile/widgets/nearby_places_sheet.dart';

NearbyPlace _place(
  String id, {
  required NearbyCategory category,
  required NearbyAnchor? anchor,
  int distance = 100,
}) {
  return NearbyPlace(
    id: id,
    name: 'Place $id',
    category: category,
    latitude: LatLng(18.52 + distance * 1e-5, 73.85).latitude,
    longitude: LatLng(18.52, 73.85 + distance * 1e-5).longitude,
    distanceMeters: distance,
    anchor: anchor,
  );
}

Future<void> _pump(WidgetTester tester, Widget sheet) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SizedBox.expand(child: sheet),
      ),
    ),
  );
}

void main() {
  testWidgets(
    'single-anchor results never render the empty placeholder section',
    (WidgetTester tester) async {
      final List<NearbyPlace> places = <NearbyPlace>[
        _place('end-1', category: NearbyCategory.police, anchor: NearbyAnchor.routeEnd),
        _place('end-2', category: NearbyCategory.hospital, anchor: NearbyAnchor.routeEnd),
      ];
      await _pump(
        tester,
        SingleChildScrollView(
          child: NearbyPlacesSheet(
            category: NearbyCategory.all,
            places: places,
            onPlaceSelected: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Rendered: the destination section with its headings.
      expect(
        find.text('Places around your destination'),
        findsOneWidget,
      );
      expect(find.text('Place end-1'), findsOneWidget);
      expect(find.text('Place end-2'), findsOneWidget);

      // Never rendered: the start section or any empty placeholder.
      expect(find.text('Places around your start point'), findsNothing);
      expect(find.text('No places found within 3 km.'), findsNothing);
      expect(find.text('Police station'), findsOneWidget);
      expect(find.text('Hospital'), findsOneWidget);
    },
  );

  testWidgets(
    'both anchors render and empty anchors are omitted',
    (WidgetTester tester) async {
      final List<NearbyPlace> places = <NearbyPlace>[
        _place('end-1', category: NearbyCategory.bus, anchor: NearbyAnchor.routeEnd),
      ];
      await _pump(
        tester,
        SingleChildScrollView(
          child: NearbyPlacesSheet(
            category: NearbyCategory.all,
            places: places,
            onPlaceSelected: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Places around your destination'), findsOneWidget);
      expect(find.text('Places around your start point'), findsNothing);
      expect(find.text('No places found within 3 km.'), findsNothing);
    },
  );

  testWidgets(
    'fully empty result set keeps one clear empty message',
    (WidgetTester tester) async {
      await _pump(
        tester,
        SingleChildScrollView(
          child: NearbyPlacesSheet(
            category: NearbyCategory.hospital,
            places: <NearbyPlace>[],
            onPlaceSelected: (_) {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('No places found within 3 km.'), findsOneWidget);
      expect(find.text('Places around your destination'), findsNothing);
      expect(find.text('Places around your start point'), findsNothing);
    },
  );
}
