class Risk {
  final double score;
  final double lighting;
  final double crowdDensity;
  final DateTime lastUpdated;

  Risk({
    required this.score,
    required this.lighting,
    required this.crowdDensity,
    required this.lastUpdated,
  });

  bool get isHighRisk => score > 0.7;
}
