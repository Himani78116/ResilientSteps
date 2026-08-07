import 'package:flutter_map/flutter_map.dart';
import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../config/app_config.dart';

class WalkSafeMapView extends StatelessWidget {
  const WalkSafeMapView({
    super.key,
    required this.initialCenter,
    this.initialZoom = 14,
    this.mapController,
    this.markers = const <Marker>[],
    this.safetyOverlays = const <CircleMarker>[],
    this.overlayLayers = const <Widget>[],
    this.routePolylines = const <Polyline>[],
    this.onTap,
    this.onPositionChanged,
    this.onMapReady,
  });

  final LatLng initialCenter;
  final double initialZoom;
  final MapController? mapController;
  final List<Marker> markers;
  final List<CircleMarker> safetyOverlays;
  final List<Widget> overlayLayers;
  final List<Polyline> routePolylines;
  final void Function(LatLng point)? onTap;
  final void Function(MapCamera camera)? onPositionChanged;
  final VoidCallback? onMapReady;

  @override
  Widget build(BuildContext context) {
    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: initialCenter,
        initialZoom: initialZoom,
        onMapReady: onMapReady,
        onTap: (_, LatLng point) => onTap?.call(point),
        onPositionChanged: (MapCamera camera, bool hasGesture) {
          onPositionChanged?.call(camera);
        },
      ),
      children: <Widget>[
        TileLayer(
          urlTemplate:
              'https://api.maptiler.com/maps/streets-v2/{z}/{x}/{y}.png'
              '?key=${AppConfig.maptilerApiKey}',
          userAgentPackageName: 'com.safewalk.mobile',
          // MapTiler uses standard 256px raster tiles for this style.
          tileDimension: 256,
          // Keep only a small tile margin loaded to reduce memory pressure on
          // low-end devices while panning around the map.
          panBuffer: 1,
          keepBuffer: 1,
          tileProvider: NetworkTileProvider(),
        ),
        if (safetyOverlays.isNotEmpty) CircleLayer(circles: safetyOverlays),
        ...overlayLayers,
        if (routePolylines.isNotEmpty) PolylineLayer(polylines: routePolylines),
        if (markers.isNotEmpty) MarkerLayer(markers: markers),
        RichAttributionWidget(
          attributions: <SourceAttribution>[
            TextSourceAttribution('MapTiler'),
            TextSourceAttribution('OpenStreetMap contributors'),
          ],
        ),
      ],
    );
  }
}
