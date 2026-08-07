class LogicSafetyScore {
  const LogicSafetyScore({
    required this.segmentId,
    required this.safetyScore,
    required this.distanceToQueryMeters,
    required this.distanceMeters,
    required this.startLat,
    required this.startLon,
    required this.endLat,
    required this.endLon,
  });

  final String segmentId;
  final double safetyScore;
  final double distanceToQueryMeters;
  final double distanceMeters;
  final double startLat;
  final double startLon;
  final double endLat;
  final double endLon;

  factory LogicSafetyScore.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> nearest =
        (json['nearest_segment'] as Map<String, dynamic>?) ??
        <String, dynamic>{};

    double toDouble(Object? value) {
      if (value is num) {
        return value.toDouble();
      }
      return double.tryParse('$value') ?? 0;
    }

    return LogicSafetyScore(
      segmentId: '${nearest['segment_id'] ?? ''}',
      safetyScore: toDouble(nearest['safety_score']),
      distanceToQueryMeters: toDouble(nearest['distance_to_query_meters']),
      distanceMeters: toDouble(nearest['distance']),
      startLat: toDouble(nearest['start_lat']),
      startLon: toDouble(nearest['start_lon']),
      endLat: toDouble(nearest['end_lat']),
      endLon: toDouble(nearest['end_lon']),
    );
  }
}
