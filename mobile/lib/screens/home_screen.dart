import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../controllers/navigation_controller.dart';
import '../models/place_suggestion.dart';
import '../models/scored_route.dart';
import '../models/safety_zone.dart';
import '../services/location_service.dart';
import '../services/navigation_math.dart';
import '../services/place_search_service.dart';
import '../services/routing_service.dart';
import '../services/safety_heatmap_service.dart';
import '../services/auth_service.dart';
import '../services/saved_places_service.dart';
import '../services/sos_service.dart';
import '../widgets/incident_modal.dart';
import '../widgets/map_layers_builder.dart';
import '../widgets/navigation_card.dart';
import '../widgets/saved_place_chips.dart';
import 'destination_search_screen.dart';
import 'login_screen.dart';
import 'settings_profile_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static final LatLng _defaultCenter = LatLng(18.5204, 73.8567);
  static const double _markerZoomUpdateThreshold = 0.05;

  final MapController _mapController = MapController();
  final LocationService _locationService = LocationService();
  final RoutingService _routingService = RoutingService();
  final SafetyHeatmapService _heatmapService = SafetyHeatmapService();
  final SosService _sosService = SosService();
  final PlaceSearchService _placeSearchService = PlaceSearchService();
  late final NavigationController _navController;
  StreamSubscription<AuthState>? _authSubscription;

  LatLng _cameraTarget = _defaultCenter;
  // Keep the last real device fix separate from the viewport center.
  LatLng _lastKnownUserPoint = _defaultCenter;
  List<SafetyZone> _safetyZones = <SafetyZone>[];
  bool _isLoadingLocation = true;
  bool _isLoadingRoute = false;
  bool _showSafetyZones = true;
  bool _mapReady = false;
  bool _isNavigationCardExpanded = false;
  double _currentZoom = 14.8;
  String? _destinationLabel;

  LatLng get _liveUserPoint =>
      _navController.liveUserPoint ?? _lastKnownUserPoint;

  bool get _showCompassReset =>
      _navController.headingUpMode && _navController.hasHeading;

  IconData get _profileIcon => AuthService.instance.isLoggedIn
      ? Icons.account_circle
      : Icons.account_circle_outlined;

  Color get _profileIconColor =>
      AuthService.instance.isLoggedIn ? Colors.blue : Colors.grey;

  String get _profileTooltip => AuthService.instance.isLoggedIn
      ? AuthService.instance.displayName
      : 'Sign in';

  List<Marker> get _markers => MapLayersBuilder.buildNavigationMarkers(
    start: _liveUserPoint,
    destination: _navController.destinationLatLng,
    destinationLabel: _destinationLabel ?? 'Destination',
    heading: _navController.currentHeading,
    zoom: _currentZoom,
  );

  List<Polyline> get _routePolylines {
    final ScoredRoute? route = _navController.selectedRoute;
    if (route == null) {
      return const <Polyline>[];
    }

    return MapLayersBuilder.buildRoutePolylines(
      route: route,
      progress: _navController.routeProgress,
      navState: _navController.navState,
    );
  }

  @override
  void initState() {
    super.initState();
    _navController = NavigationController()
      ..addListener(_handleNavigationChanged)
      ..onArrived = _handleArrived
      ..onRerouteRequired = () {
        unawaited(_handleRerouteRequired());
      }
      ..beginTracking();
    _authSubscription = AuthService.instance.authStateChanges.listen((
      AuthState event,
    ) {
      if (event.event == AuthChangeEvent.signedIn) {
        SavedPlacesService.instance.syncFromSupabase().then((_) {
          if (mounted) {
            setState(() {});
          }
        }).catchError((_) {});
      }
      if (event.event == AuthChangeEvent.signedOut && mounted) {
        setState(() {});
      }
    });
    _loadHomeMap();
  }

  @override
  void dispose() {
    _sosService.dispose();
    _authSubscription?.cancel();
    _navController.removeListener(_handleNavigationChanged);
    _navController.dispose();
    _mapController.dispose();
    super.dispose();
  }

  void _handleNavigationChanged() {
    if (!mounted) {
      return;
    }

    _applyPendingCameraInstruction();
    setState(() {
      final LatLng? liveUserPoint = _navController.liveUserPoint;
      if (liveUserPoint != null) {
        _lastKnownUserPoint = liveUserPoint;
        _cameraTarget = liveUserPoint;
      }
    });
  }

  void _handleArrived() {
    _resetMapBearing();
    if (!mounted) {
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('You have arrived at your destination.'),
        duration: Duration(seconds: 4),
      ),
    );
  }

  Future<void> _handleRerouteRequired() async {
    final LatLng? destination = _navController.destinationLatLng;
    if (destination == null) {
      _navController.completeReroute();
      return;
    }

    await _loadRoute(
      start: _liveUserPoint,
      destination: destination,
      label: _destinationLabel,
      moveCamera: false,
      preserveVisibleRoute: true,
    );
    _navController.completeReroute();
  }

  void _resetMapBearing() {
    if (_mapReady) {
      _mapController.rotate(0);
    }
  }

  Future<void> _loadHomeMap() async {
    final HomeMapLoadResult result = await _navController.loadHomeMap(
      locationService: _locationService,
      heatmapService: _heatmapService,
      fallbackCenter: _defaultCenter,
    );
    if (!mounted) {
      return;
    }

    setState(() {
      _safetyZones = result.safetyZones;
      _isLoadingLocation = false;
      _lastKnownUserPoint = result.center;
      _cameraTarget = result.center;
      _destinationLabel = null;
      _isNavigationCardExpanded = false;
    });

    _mapController.move(result.center, 15.2);
  }

  Future<void> _loadRoute({
    required LatLng start,
    required LatLng destination,
    String? label,
    bool moveCamera = true,
    bool preserveVisibleRoute = false,
  }) async {
    if (_isLoadingLocation || _isLoadingRoute) {
      return;
    }

    final bool preserveExistingRoute =
        _navController.navState == NavigationState.active &&
        preserveVisibleRoute &&
        _navController.selectedRoute != null;

    setState(() {
      _destinationLabel = label ?? _destinationLabel ?? 'Pinned destination';
      _isLoadingRoute = true;
      if (_navController.navState != NavigationState.active) {
        _isNavigationCardExpanded = false;
      }
    });

    if (moveCamera) {
      _mapController.move(destination, 15.8);
    }

    final RouteLoadResult result = await _navController.loadRoute(
      start: start,
      destination: destination,
      routingService: _routingService,
      heatmapService: _heatmapService,
      preserveVisibleRoute: preserveVisibleRoute,
    );
    if (!mounted) {
      return;
    }

    if (result.safetyZones.isNotEmpty) {
      setState(() {
        _safetyZones = result.safetyZones;
      });
    }

    if (!preserveExistingRoute && result.status == RouteLoadStatus.noRoute) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No walking route found. Try another nearby point.'),
        ),
      );
    }

    if (!preserveExistingRoute && result.status == RouteLoadStatus.error) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not find a route right now. Try another destination.',
          ),
        ),
      );
    }

    if (mounted) {
      setState(() {
        _isLoadingRoute = false;
      });
    }
  }

  Future<void> _refreshNearbySafetyZones() async {
    final List<SafetyZone> zones = await _navController
        .refreshNearbySafetyZones(
          heatmapService: _heatmapService,
          fallbackPoint: _cameraTarget,
        );
    if (!mounted || zones.isEmpty) {
      return;
    }
    setState(() {
      _safetyZones = zones;
    });
  }

  Future<void> _openDestinationSearch() async {
    final PlaceSuggestion? suggestion = await Navigator.of(context)
        .push<PlaceSuggestion>(
          MaterialPageRoute<PlaceSuggestion>(
            builder: (_) => DestinationSearchScreen(
              placeSearchService: _placeSearchService,
              initialQuery: _destinationLabel,
            ),
          ),
        );

    if (!mounted || suggestion == null) {
      return;
    }

    await _setDestination(
      suggestion.point.latitude,
      suggestion.point.longitude,
      suggestion.title,
    );
  }

  void _clearRoute() {
    setState(() {
      _destinationLabel = null;
      _isNavigationCardExpanded = false;
    });
    _navController.stopNavigation();
    unawaited(_refreshNearbySafetyZones());
    _resetMapBearing();
    _moveCameraToUser(zoom: 15.2);
  }

  void _recenterOnUser() {
    final LatLng userPoint = _liveUserPoint;
    _cameraTarget = userPoint;

    if (_navController.navState == NavigationState.active) {
      _navController.enableHeadingUpMode();
      final double zoom = _mapController.camera.zoom;
      final double? heading = _navController.hasHeading
          ? NavigationMath.normalizeHeading(_navController.currentHeading)
          : null;

      if (_navController.headingUpMode && heading != null) {
        _mapController.moveAndRotate(
          _cameraFollowTarget(userPoint, heading),
          zoom,
          -heading,
        );
      } else {
        _mapController.move(userPoint, zoom);
      }
      return;
    }

    _moveCameraToUser(zoom: 15.2);
  }

  void _toggleSafetyZones() {
    setState(() {
      _showSafetyZones = !_showSafetyZones;
    });
  }

  void _onCompassResetPressed() {
    _resetMapBearing();
    _navController.resetHeadingUpMode();
  }

  void _handleStartNavigation() {
    _navController.startRoute();
    _applyPendingCameraInstruction();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Route started. Follow the highlighted path and keep an eye on nearby danger zones.',
        ),
      ),
    );
  }

  void _handleStopNavigation() {
    setState(() {
      _destinationLabel = null;
      _isNavigationCardExpanded = false;
    });
    _navController.stopNavigation();
    _resetMapBearing();
    unawaited(_refreshNearbySafetyZones());
  }

  double _forwardLookDistanceMeters(double zoom) {
    final double scaledDistance = 24 + ((18 - zoom) * 8);
    return scaledDistance.clamp(18.0, 56.0).toDouble();
  }

  LatLng _cameraFollowTarget(LatLng userPoint, double? heading) {
    if (!_navController.headingUpMode || heading == null) {
      return userPoint;
    }

    return NavigationMath.offsetPoint(
      userPoint,
      distanceMeters: _forwardLookDistanceMeters(_currentZoom),
      headingDegrees: heading,
    );
  }

  void _applyPendingCameraInstruction() {
    if (!_mapReady) {
      return;
    }

    final NavigationCameraInstruction? instruction =
        _navController.pendingCameraInstruction;
    if (instruction == null) {
      return;
    }

    final double zoom = _mapController.camera.zoom;
    if (instruction.rotateCamera && instruction.heading != null) {
      _mapController.moveAndRotate(
        _cameraFollowTarget(instruction.userPoint, instruction.heading),
        zoom,
        -instruction.heading!,
      );
    } else {
      _mapController.move(instruction.userPoint, zoom);
    }

    _navController.markCameraInstructionHandled();
  }

  void _moveCameraToUser({required double zoom}) {
    final LatLng userPoint = _liveUserPoint;
    _cameraTarget = userPoint;
    _mapController.move(userPoint, zoom);
  }

  Future<void> _setDestination(double lat, double lon, String name) async {
    await _loadRoute(
      start: _liveUserPoint,
      destination: LatLng(lat, lon),
      label: name,
    );
  }

  void _showAuthRequiredDialog(
    BuildContext context, {
    required String feature,
    required String reason,
  }) {
    showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: const Text('Sign in required'),
        content: Text('$feature requires a WalkSafe account.\n\n$reason'),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Not now'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              Navigator.of(context).push(
                MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
              );
            },
            child: const Text('Sign in'),
          ),
        ],
      ),
    );
  }

  Future<void> _openIncidentReport() async {
    if (!AuthService.instance.isLoggedIn) {
      _showAuthRequiredDialog(
        context,
        feature: 'Incident reporting',
        reason:
            'Reports are linked to your account so the community can trust them.',
      );
      return;
    }

    await showIncidentReportDialog(
      context: context,
      initialLocation: _navController.destinationLatLng ?? _cameraTarget,
    );
  }

  Future<void> _triggerSos() async {
    if (!AuthService.instance.isLoggedIn) {
      _showAuthRequiredDialog(
        context,
        feature: 'SOS alerts',
        reason:
            'SOS requires an account to link your trusted contacts and location.',
      );
      return;
    }

    await showSosIncidentDialog(context: context, sosService: _sosService);
  }

  void _openProfileScreen() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AuthService.instance.isLoggedIn
            ? const SettingsProfileScreen()
            : const LoginScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final NavigationState navState = _navController.navState;
    final bool showBottomCard =
        _isLoadingRoute ||
        navState == NavigationState.planning ||
        navState == NavigationState.active ||
        navState == NavigationState.arrived;
    final double actionBottomOffset =
        navState == NavigationState.active && !_isNavigationCardExpanded
        ? 104
        : showBottomCard
        ? 288
        : 28;

    return Scaffold(
      body: HomeScreenBody(
        mapController: _mapController,
        initialCenter: _cameraTarget,
        safetyZones: _safetyZones,
        showSafetyZones: _showSafetyZones,
        routePolylines: _routePolylines,
        markers: _markers,
        destinationLabel: _destinationLabel,
        isLoadingRoute: _isLoadingRoute,
        isLoadingLocation: _isLoadingLocation,
        showHintChip: _navController.selectedRoute == null && !_isLoadingRoute,
        showCompassReset: _showCompassReset,
        actionBottomOffset: actionBottomOffset,
        navState: navState,
        route: _navController.selectedRoute,
        isRerouting: _navController.isRerouting,
        savedPlacesBar: AuthService.instance.isLoggedIn
            ? SavedPlaceChips(
                onPlaceSelected: (
                  double lat,
                  double lon,
                  String name,
                ) => _setDestination(lat, lon, name),
              )
            : null,
        onMapReady: () {
          _mapReady = true;
          _applyPendingCameraInstruction();
          if (mounted) {
            setState(() {});
          }
        },
        onMapTap: (LatLng point) {
          _setDestination(
            point.latitude,
            point.longitude,
            'Pinned destination',
          );
        },
        onPositionChanged: (MapCamera camera) {
          _cameraTarget = camera.center;
          final double zoomDelta = (camera.zoom - _currentZoom).abs();
          if (zoomDelta < _markerZoomUpdateThreshold) {
            _currentZoom = camera.zoom;
            return;
          }

          if (!mounted) {
            _currentZoom = camera.zoom;
            return;
          }

          setState(() {
            _currentZoom = camera.zoom;
          });
        },
        onRecenter: _recenterOnUser,
        onSearchTap: _openDestinationSearch,
        onClearRoute: _destinationLabel == null || _isLoadingRoute
            ? null
            : _clearRoute,
        profileIcon: _profileIcon,
        profileIconColor: _profileIconColor,
        profileTooltip: _profileTooltip,
        onOpenProfile: _openProfileScreen,
        onToggleSafetyZones: _toggleSafetyZones,
        onResetCompass: _onCompassResetPressed,
        onReportIncident: _openIncidentReport,
        onTriggerSos: _triggerSos,
        onStartNavigation: _handleStartNavigation,
        onStopNavigation: _handleStopNavigation,
        onDismissArrival: _handleStopNavigation,
        onCardExpansionChanged: (bool isExpanded) {
          if (_isNavigationCardExpanded == isExpanded) {
            return;
          }
          setState(() {
            _isNavigationCardExpanded = isExpanded;
          });
        },
      ),
    );
  }
}
