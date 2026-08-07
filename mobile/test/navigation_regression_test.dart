import 'dart:async';

import 'package:flutter_compass/flutter_compass.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:mobile/controllers/navigation_controller.dart';
import 'package:mobile/models/route_segment_safety.dart';
import 'package:mobile/models/scored_route.dart';
import 'package:mobile/widgets/map_layers_builder.dart';

void main() {
  group('Navigation regression', () {
    test('user marker follows GPS input instead of map center', () async {
      final StreamController<Position> positionUpdates =
          StreamController<Position>();
      final NavigationController controller = NavigationController(
        positionStreamFactory: () => positionUpdates.stream,
        compassStreamFactory: () => const Stream<CompassEvent>.empty(),
      );
      addTearDown(() async {
        controller.dispose();
        await positionUpdates.close();
      });

      controller.beginTracking();

      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8560, heading: 90),
      );
      await _flushEvents();

      positionUpdates.add(
        _position(latitude: 18.5212, longitude: 73.8574, heading: 95),
      );
      await _flushEvents();

      const LatLng mapCenter = LatLng(18.5300, 73.8700);
      final markers = MapLayersBuilder.buildNavigationMarkers(
        start: controller.liveUserPoint!,
        destination: null,
        destinationLabel: 'Destination',
        heading: controller.currentHeading,
        zoom: 15.0,
      );

      expect(markers, hasLength(1));
      expect(markers.first.point.latitude, closeTo(18.5212, 0.000001));
      expect(markers.first.point.longitude, closeTo(73.8574, 0.000001));
      expect(markers.first.point.latitude, isNot(closeTo(mapCenter.latitude, 0.000001)));
      expect(
        markers.first.point.longitude,
        isNot(closeTo(mapCenter.longitude, 0.000001)),
      );
    });

    test('recenter targets the current user position', () async {
      final StreamController<Position> positionUpdates =
          StreamController<Position>();
      final NavigationController controller = NavigationController(
        positionStreamFactory: () => positionUpdates.stream,
        compassStreamFactory: () => const Stream<CompassEvent>.empty(),
      );
      addTearDown(() async {
        controller.dispose();
        await positionUpdates.close();
      });

      controller.beginTracking();
      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8560, heading: 48),
      );
      await _flushEvents();

      controller.applyLoadedRoute(
        route: _buildRoute(),
        destination: const LatLng(18.5200, 73.8580),
        keepActive: false,
      );
      controller.startRoute();
      controller.markCameraInstructionHandled();
      controller.resetHeadingUpMode();

      controller.enableHeadingUpMode();

      final instruction = controller.pendingCameraInstruction;
      expect(instruction, isNotNull);
      expect(instruction!.userPoint.latitude, closeTo(18.5200, 0.000001));
      expect(instruction.userPoint.longitude, closeTo(73.8560, 0.000001));
      expect(instruction.rotateCamera, isTrue);
      expect(instruction.heading, isNotNull);
    });

    test('starting navigation enables follow mode', () async {
      final StreamController<Position> positionUpdates =
          StreamController<Position>();
      final NavigationController controller = NavigationController(
        positionStreamFactory: () => positionUpdates.stream,
        compassStreamFactory: () => const Stream<CompassEvent>.empty(),
      );
      addTearDown(() async {
        controller.dispose();
        await positionUpdates.close();
      });

      controller.beginTracking();
      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8560, heading: 32),
      );
      await _flushEvents();

      controller.applyLoadedRoute(
        route: _buildRoute(),
        destination: const LatLng(18.5200, 73.8580),
        keepActive: false,
      );

      controller.startRoute();

      expect(controller.navState, NavigationState.active);
      expect(controller.headingUpMode, isTrue);
      expect(controller.pendingCameraInstruction, isNotNull);
      expect(controller.pendingCameraInstruction!.rotateCamera, isTrue);
    });

    test('stopping navigation clears route and resets state', () async {
      final StreamController<Position> positionUpdates =
          StreamController<Position>();
      final NavigationController controller = NavigationController(
        positionStreamFactory: () => positionUpdates.stream,
        compassStreamFactory: () => const Stream<CompassEvent>.empty(),
      );
      addTearDown(() async {
        controller.dispose();
        await positionUpdates.close();
      });

      controller.beginTracking();
      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8560, heading: 32),
      );
      await _flushEvents();

      controller.applyLoadedRoute(
        route: _buildRoute(),
        destination: const LatLng(18.5200, 73.8580),
        keepActive: false,
      );
      controller.startRoute();

      controller.stopNavigation();

      expect(controller.navState, NavigationState.idle);
      expect(controller.destinationLatLng, isNull);
      expect(controller.selectedRoute, isNull);
      expect(controller.currentRoute, isNull);
      expect(controller.routeProgress, isNull);
      expect(controller.headingUpMode, isFalse);
      expect(controller.pendingCameraInstruction, isNull);
    });

    test('route progress updates as mocked positions move along the route', () async {
      final StreamController<Position> positionUpdates =
          StreamController<Position>();
      final NavigationController controller = NavigationController(
        positionStreamFactory: () => positionUpdates.stream,
        compassStreamFactory: () => const Stream<CompassEvent>.empty(),
      );
      addTearDown(() async {
        controller.dispose();
        await positionUpdates.close();
      });

      controller.beginTracking();
      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8560, heading: 90),
      );
      await _flushEvents();

      controller.applyLoadedRoute(
        route: _buildRoute(),
        destination: const LatLng(18.5200, 73.8580),
        keepActive: false,
      );
      controller.startRoute();

      final initialProgress = controller.routeProgress;
      expect(initialProgress, isNotNull);

      positionUpdates.add(
        _position(latitude: 18.5200, longitude: 73.8572, heading: 90),
      );
      await _flushEvents();

      final updatedProgress = controller.routeProgress;
      expect(updatedProgress, isNotNull);
      expect(
        updatedProgress!.distanceAlongRouteMeters,
        greaterThan(initialProgress!.distanceAlongRouteMeters),
      );
      expect(
        controller.lastProgressPosition!.longitude,
        closeTo(73.8572, 0.000001),
      );
      expect(updatedProgress.remainingPoints.length, lessThanOrEqualTo(2));
    });
  });
}

Future<void> _flushEvents() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

Position _position({
  required double latitude,
  required double longitude,
  required double heading,
}) {
  return Position(
    latitude: latitude,
    longitude: longitude,
    timestamp: DateTime.utc(2026, 4, 6, 12),
    accuracy: 5,
    altitude: 0,
    altitudeAccuracy: 0,
    heading: heading,
    headingAccuracy: 5,
    speed: 1.4,
    speedAccuracy: 0.2,
  );
}

ScoredRoute _buildRoute() {
  return const ScoredRoute(
    points: [
      LatLng(18.5200, 73.8560),
      LatLng(18.5200, 73.8570),
      LatLng(18.5200, 73.8580),
    ],
    segments: [
      RouteSegmentSafety(
        start: LatLng(18.5200, 73.8560),
        end: LatLng(18.5200, 73.8570),
        distanceMeters: 110,
        safetyScore: 82,
        incidentRisk: 0.1,
        timeOfDayRisk: 0.1,
        lightingLevel: 0.8,
        crowdDensity: 0.4,
        distanceWeight: 1,
        safetyPenalty: 2,
        risk: 3,
        safetyLevel: 'SAFE',
      ),
      RouteSegmentSafety(
        start: LatLng(18.5200, 73.8570),
        end: LatLng(18.5200, 73.8580),
        distanceMeters: 110,
        safetyScore: 76,
        incidentRisk: 0.2,
        timeOfDayRisk: 0.1,
        lightingLevel: 0.7,
        crowdDensity: 0.5,
        distanceWeight: 1,
        safetyPenalty: 3,
        risk: 4,
        safetyLevel: 'SAFE',
      ),
    ],
    totalDistanceMeters: 220,
    averageSafetyScore: 79,
    totalRisk: 7,
  );
}
