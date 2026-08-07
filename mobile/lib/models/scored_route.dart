import 'package:latlong2/latlong.dart';

import 'route_segment_safety.dart';

class ScoredRoute {
  const ScoredRoute({
    required this.points,
    required this.segments,
    required this.totalDistanceMeters,
    required this.averageSafetyScore,
    required this.totalRisk,
    this.durationMinutes,
    this.warning,
  });

  final List<LatLng> points;
  final List<RouteSegmentSafety> segments;
  final double totalDistanceMeters;
  final double averageSafetyScore;
  final double totalRisk;
  final double? durationMinutes;
  final String? warning;
}
