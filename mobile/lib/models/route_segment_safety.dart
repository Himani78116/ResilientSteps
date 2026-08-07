import 'package:latlong2/latlong.dart';

class RouteSegmentSafety {
  const RouteSegmentSafety({
    required this.start,
    required this.end,
    required this.distanceMeters,
    required this.safetyScore,
    required this.incidentRisk,
    required this.timeOfDayRisk,
    required this.lightingLevel,
    required this.crowdDensity,
    required this.distanceWeight,
    required this.safetyPenalty,
    required this.risk,
    this.segmentId,
    this.safetyLevel,
    this.baseSafetyScore,
    this.incidentDensity,
    this.lightingHeuristic,
    this.timePenalty,
    this.distanceToQuery,
  });

  final LatLng start;
  final LatLng end;
  final double distanceMeters;

  // Normalized segment safety score from 0 (unsafe) to 100 (safe).
  final double safetyScore;

  // Factor contributions used by the scoring engine.
  final double incidentRisk;
  final double timeOfDayRisk;
  final double lightingLevel;
  final double crowdDensity;

  // Risk formula terms:
  // risk = distance_weight + safety_penalty
  final double distanceWeight;
  final double safetyPenalty;
  final double risk;

  // Backend-supplied metadata for rendering/diagnostics.
  final String? segmentId;
  final String? safetyLevel;
  final double? baseSafetyScore;
  final double? incidentDensity;
  final double? lightingHeuristic;
  final double? timePenalty;
  final double? distanceToQuery;
}
