import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../models/safety_zone.dart';

class SafetyZoneOverlay extends StatelessWidget {
  const SafetyZoneOverlay({
    super.key,
    required this.zones,
  });

  final List<SafetyZone> zones;

  @override
  Widget build(BuildContext context) {
    if (zones.isEmpty) {
      return const SizedBox.shrink();
    }

    final List<Polygon> polygons = zones
        .map(_buildPolygon)
        .whereType<Polygon>()
        .toList(growable: false);

    return IgnorePointer(child: PolygonLayer(polygons: polygons));
  }

  Polygon? _buildPolygon(SafetyZone zone) {
    if (zone.polygonPoints.length < 3) {
      return null;
    }

    final _ZonePolygonStyle style = _styleForZone(zone.classification);
    return Polygon(
      points: zone.polygonPoints,
      color: style.fillColor.withValues(alpha: style.fillOpacity),
      borderColor: style.borderColor,
      borderStrokeWidth: style.borderWidth,
    );
  }

  _ZonePolygonStyle _styleForZone(String? classification) {
    switch ((classification ?? '').toLowerCase()) {
      case 'safe':
        return const _ZonePolygonStyle(
          fillColor: Color(0xFF43A047),
          fillOpacity: 0.28,
          borderColor: Color(0xFF43A047),
          borderWidth: 1,
        );
      case 'cautious':
        return const _ZonePolygonStyle(
          fillColor: Color(0xFFF57C00),
          fillOpacity: 0.32,
          borderColor: Color(0xFFF57C00),
          borderWidth: 1,
        );
      case 'risky':
        return const _ZonePolygonStyle(
          fillColor: Color(0xFFD32F2F),
          fillOpacity: 0.38,
          borderColor: Color(0xFFD32F2F),
          borderWidth: 1.5,
        );
      default:
        return const _ZonePolygonStyle(
          fillColor: Color(0xFF9E9E9E),
          fillOpacity: 0.20,
          borderColor: Color(0xFF9E9E9E),
          borderWidth: 1,
        );
    }
  }
}

class _ZonePolygonStyle {
  const _ZonePolygonStyle({
    required this.fillColor,
    required this.fillOpacity,
    required this.borderColor,
    required this.borderWidth,
  });

  final Color fillColor;
  final double fillOpacity;
  final Color borderColor;
  final double borderWidth;
}
