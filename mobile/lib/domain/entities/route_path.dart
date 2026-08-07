import 'package:latlong2/latlong.dart';
import 'risk.dart';

class RoutePath {
  final String id;
  final List<LatLng> points;
  final double totalDistance;
  final double safetyScore;
  final List<Risk> riskSegments;

  RoutePath({
    required this.id,
    required this.points,
    required this.totalDistance,
    required this.safetyScore,
    required this.riskSegments,
  });
}
