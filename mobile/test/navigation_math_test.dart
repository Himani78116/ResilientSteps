import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/services/navigation_math.dart';

void main() {
  group('NavigationMath', () {
    test('distanceToPolylineMeters measures against line segments', () {
      final List<LatLng> routePoints = <LatLng>[
        const LatLng(18.5200, 73.8560),
        const LatLng(18.5200, 73.8570),
      ];

      final double distance = NavigationMath.distanceToPolylineMeters(
        const LatLng(18.5201, 73.8565),
        routePoints,
      );

      expect(distance, greaterThan(8));
      expect(distance, lessThan(15));
    });

    test('blendHeading keeps wrap-around transitions smooth', () {
      final double blended = NavigationMath.blendHeading(350, 10, factor: 0.5);

      expect(blended, closeTo(0, 0.001));
    });

    test('rerouteThresholdMeters respects min and max bounds', () {
      expect(NavigationMath.rerouteThresholdMeters(5), 40);
      expect(NavigationMath.rerouteThresholdMeters(50), 80);
      expect(NavigationMath.rerouteThresholdMeters(20), 44);
    });
  });
}
