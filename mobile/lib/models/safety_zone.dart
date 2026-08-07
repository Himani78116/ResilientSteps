import 'package:latlong2/latlong.dart';

enum SafetyLevel { risky, cautious, safe }

class SafetyZone {
  const SafetyZone({
    required this.id,
    required this.latitude,
    required this.longitude,
    required this.safetyScore,
    this.radiusMeters = 120,
    this.classification,
    this.polygonPoints = const <LatLng>[],
  });

  final String id;
  final double latitude;
  final double longitude;
  final double safetyScore;
  final double radiusMeters;
  final String? classification;
  final List<LatLng> polygonPoints;

  factory SafetyZone.fromJson(Map<String, dynamic> json) {
    double parseDouble(Object? value, {double fallback = 0}) {
      if (value is num) {
        return value.toDouble();
      }
      if (value is String) {
        return double.tryParse(value) ?? fallback;
      }
      return fallback;
    }

    List<LatLng> parsePolygonPoints(Object? value) {
      if (value is! List) {
        return const <LatLng>[];
      }

      final List<LatLng> points = <LatLng>[];
      for (final dynamic item in value) {
        if (item is! List || item.length < 2) {
          continue;
        }

        final double lon = parseDouble(item[0], fallback: double.nan);
        final double lat = parseDouble(item[1], fallback: double.nan);
        if (lat.isNaN || lon.isNaN) {
          continue;
        }
        points.add(LatLng(lat, lon));
      }
      return points;
    }

    return SafetyZone(
      id: '${json['id'] ?? ''}',
      latitude: parseDouble(json['lat'] ?? json['latitude']),
      longitude: parseDouble(json['lon'] ?? json['longitude']),
      safetyScore: parseDouble(json['score'] ?? json['safetyScore']),
      radiusMeters: parseDouble(
        json['radius_meters'] ?? json['radiusMeters'],
        fallback: 120,
      ),
      classification: json['classification']?.toString(),
      polygonPoints: parsePolygonPoints(json['polygon_points']),
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'lat': latitude,
      'lon': longitude,
      'score': safetyScore,
      'radius_meters': radiusMeters,
      'classification': classification,
      'polygon_points': polygonPoints
          .map(
            (LatLng point) => <double>[point.longitude, point.latitude],
          )
          .toList(growable: false),
    };
  }

  // Converts a numeric score into one of three safety classes.
  SafetyLevel get safetyLevel {
    final String normalized = (classification ?? '').toUpperCase();
    if (normalized == 'SAFE') {
      return SafetyLevel.safe;
    }
    if (normalized == 'CAUTIOUS') {
      return SafetyLevel.cautious;
    }
    if (normalized == 'RISKY') {
      return SafetyLevel.risky;
    }

    if (safetyScore < 40) {
      return SafetyLevel.risky;
    }
    if (safetyScore < 70) {
      return SafetyLevel.cautious;
    }
    return SafetyLevel.safe;
  }
}
