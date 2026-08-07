import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../controllers/navigation_controller.dart';
import '../models/route_segment_safety.dart';
import '../models/scored_route.dart';
import '../services/navigation_math.dart';

class MapLayersBuilder {
  MapLayersBuilder._();

  static const LinearGradient _userMarkerGradient = LinearGradient(
    colors: <Color>[Color(0xFF34B3FF), Color(0xFF2E7CF6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  static const Border _userMarkerBorder = Border.fromBorderSide(
    BorderSide(color: Colors.white, width: 4),
  );
  static const List<BoxShadow> _userMarkerShadows = <BoxShadow>[
    BoxShadow(
      color: Color(0x422E7CF6),
      blurRadius: 20,
      offset: Offset(0, 10),
    ),
  ];
  static const BoxDecoration _destinationMarkerDecoration = BoxDecoration(
    shape: BoxShape.circle,
    color: Colors.white,
    border: Border.fromBorderSide(
      BorderSide(color: Color(0xFF2E7CF6), width: 5),
    ),
    boxShadow: <BoxShadow>[
      BoxShadow(
        color: Color(0x24000000),
        blurRadius: 18,
        offset: Offset(0, 10),
      ),
    ],
  );

  static List<Polyline> buildRoutePolylines({
    required ScoredRoute route,
    required RouteProgressSplit? progress,
    required NavigationState navState,
  }) {
    final List<LatLng> routePoints = route.points;
    if (routePoints.isEmpty) {
      return const <Polyline>[];
    }

    final List<RouteSegmentSafety> scoredSegments = route.segments
        .where((RouteSegmentSafety segment) => segment.safetyLevel != 'UNKNOWN')
        .toList(growable: false);
    final List<Polyline> polylines = <Polyline>[];
    final bool showActiveProgress =
        progress != null &&
        (navState == NavigationState.active ||
            navState == NavigationState.arrived);

    if (showActiveProgress) {
      if (progress.completedPoints.length > 1) {
        polylines.addAll(<Polyline>[
          Polyline(
            points: progress.completedPoints,
            strokeWidth: 11,
            color: Colors.white.withValues(alpha: 0.28),
          ),
          Polyline(
            points: progress.completedPoints,
            strokeWidth: 6,
            color: const Color(0xFF2F6EF6).withValues(alpha: 0.10),
          ),
        ]);
      }

      final List<LatLng> remainingPoints = progress.remainingPoints.length > 1
          ? progress.remainingPoints
          : routePoints;
      polylines.addAll(<Polyline>[
        Polyline(
          points: remainingPoints,
          strokeWidth: 16,
          color: Colors.white.withValues(alpha: 0.88),
        ),
        Polyline(
          points: remainingPoints,
          strokeWidth: 11,
          color: const Color(0xFF2F6EF6).withValues(alpha: 0.18),
        ),
      ]);

      if (scoredSegments.isEmpty) {
        polylines.add(
          Polyline(
            points: remainingPoints,
            strokeWidth: 8,
            color: const Color(0xFF30C56A),
            borderStrokeWidth: 4.4,
            borderColor: Colors.white.withValues(alpha: 0.96),
          ),
        );
        return polylines;
      }

      polylines.addAll(_buildActiveRouteSegmentOverlays(route, progress));
      return polylines;
    }

    polylines.addAll(<Polyline>[
      Polyline(
        points: routePoints,
        strokeWidth: 16,
        color: Colors.white.withValues(alpha: 0.84),
      ),
      Polyline(
        points: routePoints,
        strokeWidth: 11,
        color: const Color(0xFF2F6EF6).withValues(alpha: 0.14),
      ),
    ]);

    if (scoredSegments.isEmpty) {
      polylines.add(
        Polyline(
          points: routePoints,
          strokeWidth: 8,
          color: const Color(0xFF30C56A),
          borderStrokeWidth: 4.4,
          borderColor: Colors.white.withValues(alpha: 0.96),
        ),
      );
      return polylines;
    }

    for (final RouteSegmentSafety segment in scoredSegments) {
      polylines.add(
        Polyline(
          points: <LatLng>[segment.start, segment.end],
          strokeWidth: 8.2,
          color: _routeSegmentColor(segment),
          borderStrokeWidth: 2.8,
          borderColor: Colors.white.withValues(alpha: 0.90),
        ),
      );
    }

    return polylines;
  }

  static List<Marker> buildNavigationMarkers({
    required LatLng start,
    required LatLng? destination,
    required String destinationLabel,
    required double heading,
    required double zoom,
  }) {
    final double userMarkerDiameter = _userMarkerDiameterForZoom(zoom);
    final double userMarkerFrame = _userMarkerFrameForZoom(zoom);
    final double userIconSize = (userMarkerDiameter * 0.46)
        .clamp(18.0, 24.0)
        .toDouble();
    final List<Marker> markers = <Marker>[
      _buildMapMarker(
        point: start,
        label: 'Your location',
        size: userMarkerFrame,
        child: Container(
          width: userMarkerDiameter,
          height: userMarkerDiameter,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: _userMarkerGradient,
            border: _userMarkerBorder,
            boxShadow: _userMarkerShadows,
          ),
          child: Transform.rotate(
            angle: heading * math.pi / 180,
            child: Icon(
              Icons.navigation_rounded,
              color: Colors.white,
              size: userIconSize,
            ),
          ),
        ),
      ),
    ];

    if (destination != null) {
      markers.add(
        _buildMapMarker(
          point: destination,
          label: destinationLabel,
          child: Container(
            width: 52,
            height: 52,
            decoration: _destinationMarkerDecoration,
            child: Center(
              child: Container(
                width: 12,
                height: 12,
                decoration: const BoxDecoration(
                  color: Color(0xFF2E7CF6),
                  shape: BoxShape.circle,
                ),
              ),
            ),
          ),
        ),
      );
    }

    return markers;
  }

  static List<Polyline> _buildActiveRouteSegmentOverlays(
    ScoredRoute route,
    RouteProgressSplit progress,
  ) {
    if (route.segments.isEmpty) {
      return const <Polyline>[];
    }

    final double totalRouteDistance = NavigationMath.polylineDistanceMeters(
      route.points,
    );
    if (totalRouteDistance <= 0) {
      return const <Polyline>[];
    }

    double totalSegmentDistance = 0;
    for (final RouteSegmentSafety segment in route.segments) {
      totalSegmentDistance += _routeSegmentDistance(segment);
    }
    if (totalSegmentDistance <= 0) {
      return const <Polyline>[];
    }

    final double completedRatio =
        (progress.distanceAlongRouteMeters / totalRouteDistance)
            .clamp(0.0, 1.0)
            .toDouble();
    final double completedSegmentDistance =
        totalSegmentDistance * completedRatio;
    final List<Polyline> overlays = <Polyline>[];

    double traveled = 0;
    for (final RouteSegmentSafety segment in route.segments) {
      final double segmentDistance = _routeSegmentDistance(segment);
      final double segmentStart = traveled;
      final double segmentEnd = traveled + segmentDistance;
      traveled = segmentEnd;

      if (segment.safetyLevel == 'UNKNOWN' || segmentDistance <= 0) {
        continue;
      }
      if (completedSegmentDistance >= segmentEnd) {
        continue;
      }

      LatLng overlayStart = segment.start;
      if (completedSegmentDistance > segmentStart) {
        final double t =
            ((completedSegmentDistance - segmentStart) / segmentDistance)
                .clamp(0.0, 1.0)
                .toDouble();
        overlayStart = NavigationMath.interpolateBetween(
          segment.start,
          segment.end,
          t,
        );
      }

      if (NavigationMath.distanceMeters(overlayStart, segment.end) < 0.5) {
        continue;
      }

      overlays.add(
        Polyline(
          points: <LatLng>[overlayStart, segment.end],
          strokeWidth: 8.2,
          color: _routeSegmentColor(segment),
          borderStrokeWidth: 2.8,
          borderColor: Colors.white.withValues(alpha: 0.92),
        ),
      );
    }

    return overlays;
  }

  static double _routeSegmentDistance(RouteSegmentSafety segment) {
    if (segment.distanceMeters > 0) {
      return segment.distanceMeters;
    }
    return NavigationMath.distanceMeters(segment.start, segment.end);
  }

  static Color _routeSegmentColor(RouteSegmentSafety segment) {
    if (segment.safetyPenalty >= 8 || segment.incidentRisk >= 0.6) {
      return const Color(0xFFE24A3B);
    }
    if (segment.safetyScore >= 75) {
      return const Color(0xFF30C56A);
    }
    if (segment.safetyScore >= 55) {
      return const Color(0xFFF2A53B);
    }
    return const Color(0xFFD7644F);
  }

  static double _userMarkerDiameterForZoom(double zoom) {
    final double scaledDiameter = 36 + ((19 - zoom) * 4);
    return scaledDiameter.clamp(36.0, 56.0).toDouble();
  }

  static double _userMarkerFrameForZoom(double zoom) =>
      _userMarkerDiameterForZoom(zoom) + 12;

  static Marker _buildMapMarker({
    required LatLng point,
    required String label,
    required Widget child,
    double size = 64,
  }) {
    return Marker(
      point: point,
      width: size,
      height: size,
      child: Tooltip(
        message: label,
        child: Center(child: child),
      ),
    );
  }
}
