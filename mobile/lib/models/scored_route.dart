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
    this.comfortScore,
    this.comfortLevel,
  });

  final List<LatLng> points;
  final List<RouteSegmentSafety> segments;
  final double totalDistanceMeters;
  final double averageSafetyScore;
  final double totalRisk;
  final double? durationMinutes;
  final String? warning;
  final double? comfortScore;
  final String? comfortLevel;

  /// Human-readable comfort summary, or null when the backend has no comfort
  /// data for this route. The UI keeps its existing rendering path when null.
  String? get comfortSummary {
    final double? score = comfortScore;
    if (score == null) {
      return null;
    }

    final List<String> reasons = <String>[];
    final List<double> shadeValues = segments
        .map((RouteSegmentSafety segment) => segment.shadeScore)
        .whereType<double>()
        .toList(growable: false);
    if (shadeValues.isNotEmpty) {
      final double averageShade =
          shadeValues.reduce((double a, double b) => a + b) /
          shadeValues.length;
      if (averageShade >= 60) {
        reasons.add('well shaded');
      } else if (averageShade >= 30) {
        reasons.add('some shade');
      } else {
        reasons.add('little shade');
      }
    }

    final List<double> heatValues = segments
        .map((RouteSegmentSafety segment) => segment.heatPenalty)
        .whereType<double>()
        .toList(growable: false);
    if (heatValues.isNotEmpty) {
      final double maxHeat = heatValues.reduce(
        (double a, double b) => a > b ? a : b,
      );
      if (maxHeat >= 20) {
        reasons.add('high heat');
      } else if (maxHeat >= 5) {
        reasons.add('moderate heat');
      } else {
        reasons.add('low heat');
      }
    }

    final String? detail = reasons.isNotEmpty
        ? reasons.join(', ')
        : comfortLevel;
    final String suffix = detail == null || detail.trim().isEmpty
        ? ''
        : ' — $detail';
    return '${score.round()}% comfortable$suffix';
  }
}
