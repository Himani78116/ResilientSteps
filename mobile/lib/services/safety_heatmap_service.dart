import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/safety_zone.dart';
import 'api_utils.dart' as api_utils;

class SafetyHeatmapService {
  SafetyHeatmapService({http.Client? client, String? apiBaseUrl})
    : _client = client ?? http.Client(),
      _apiBaseUrl = apiBaseUrl ?? _baseUrl;

  static const String _baseUrl = String.fromEnvironment('API_BASE_URL');
  static const Duration _timeout = Duration(seconds: 10);
  static const String _zonesCacheKey = 'walksafe_safety_zones_cache';

  final http.Client _client;
  final String _apiBaseUrl;

  Future<List<SafetyZone>> loadSafetyZones({
    bool refresh = false,
    double? minLat,
    double? maxLat,
    double? minLon,
    double? maxLon,
  }) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final List<SafetyZone> cachedZones = _loadCachedZones(prefs);

    final Uri uri = Uri.parse('$_apiBaseUrl/safety-zones').replace(
      queryParameters: <String, String>{
        if (refresh) 'refresh': 'true',
        if (minLat != null) 'min_lat': minLat.toString(),
        if (maxLat != null) 'max_lat': maxLat.toString(),
        if (minLon != null) 'min_lon': minLon.toString(),
        if (maxLon != null) 'max_lon': maxLon.toString(),
      },
    );

    try {
      final http.Response response = await _client.get(uri).timeout(_timeout);
      if (response.statusCode == 200) {
        final Map<String, dynamic>? payload = _parseJsonMap(response.body);
        if (payload != null) {
          final List<SafetyZone> zones = _parseZones(payload['features']);
          if (zones.isNotEmpty) {
            await _cacheZones(prefs, zones: _mergeZones(cachedZones, zones));
            return zones;
          }
        }
      }
    } catch (e) {
      debugPrint('SafetyHeatmapService: failed to load safety zones: $e');
      // Fall through to cache.
    }

    return _filterZones(
      cachedZones,
      minLat: minLat,
      maxLat: maxLat,
      minLon: minLon,
      maxLon: maxLon,
    );
  }

  Future<List<SafetyZone>> loadSafetyZonesForPoints(
    List<LatLng> points, {
    bool refresh = false,
    double paddingDegrees = 0.003,
  }) async {
    final _Bounds? bounds = _boundsFromPoints(
      points,
      paddingDegrees: paddingDegrees,
    );
    if (bounds == null) {
      return loadSafetyZones(refresh: refresh);
    }

    return loadSafetyZones(
      refresh: refresh,
      minLat: bounds.minLat,
      maxLat: bounds.maxLat,
      minLon: bounds.minLon,
      maxLon: bounds.maxLon,
    );
  }

  Future<void> _cacheZones(
    SharedPreferences prefs, {
    required List<SafetyZone> zones,
  }) async {
    final List<Map<String, dynamic>> serialized = zones
        .map((SafetyZone zone) => zone.toJson())
        .toList(growable: false);
    await prefs.setString(_zonesCacheKey, jsonEncode(serialized));
  }

  List<SafetyZone> _loadCachedZones(SharedPreferences prefs) {
    final String? raw = prefs.getString(_zonesCacheKey);
    if (raw == null || raw.isEmpty) {
      return <SafetyZone>[];
    }

    try {
      final dynamic decoded = jsonDecode(raw);
      if (decoded is! List) {
        return <SafetyZone>[];
      }
      return decoded
          .whereType<Map>()
          .map(
            (Map item) => SafetyZone.fromJson(
              item.map(
                (dynamic key, dynamic value) => MapEntry(key.toString(), value),
              ),
            ),
          )
          .toList(growable: false);
    } catch (e) {
      debugPrint('SafetyHeatmapService: failed to decode cached zones: $e');
      return <SafetyZone>[];
    }
  }

  Map<String, dynamic>? _parseJsonMap(String body) =>
      api_utils.tryParseJsonMap(body);


  List<SafetyZone> _parseZones(Object? rawFeatures) {
    if (rawFeatures is! List) {
      return <SafetyZone>[];
    }

    final List<SafetyZone> zones = <SafetyZone>[];
    for (final dynamic item in rawFeatures) {
      final Map<String, dynamic>? feature = _coerceMap(item);
      final Map<String, dynamic>? properties = _coerceMap(
        feature?['properties'],
      );
      final Map<String, dynamic>? geometry = _coerceMap(feature?['geometry']);
      if (properties == null || geometry == null) {
        continue;
      }

      final List<LatLng> polygonPoints = _polygonPoints(geometry['coordinates']);
      final List<double>? centroid = _polygonCentroid(polygonPoints);
      if (centroid == null || polygonPoints.length < 3) {
        continue;
      }

      final double riskScore = _asDouble(properties['risk_score']) ?? 0;
      final String classification = _normalizeClassification(
        properties['risk_level']?.toString(),
        riskScore,
      );
      zones.add(
        SafetyZone(
          id: properties['zone_id']?.toString() ?? '',
          latitude: centroid[0],
          longitude: centroid[1],
          safetyScore: _safetyScoreFromRisk(riskScore),
          radiusMeters: _radiusMetersForRisk(riskScore, classification),
          classification: classification,
          polygonPoints: polygonPoints,
        ),
      );
    }
    return zones;
  }

  List<SafetyZone> _mergeZones(
    List<SafetyZone> existing,
    List<SafetyZone> fresh,
  ) {
    final Map<String, SafetyZone> merged = <String, SafetyZone>{
      for (final SafetyZone zone in existing) zone.id: zone,
    };
    for (final SafetyZone zone in fresh) {
      merged[zone.id] = zone;
    }
    final List<SafetyZone> mergedList = merged.values.toList();
    if (mergedList.length > 1000) {
      return mergedList.sublist(mergedList.length - 1000).toList(growable: false);
    }
    return mergedList.toList(growable: false);
  }

  List<SafetyZone> _filterZones(
    List<SafetyZone> zones, {
    double? minLat,
    double? maxLat,
    double? minLon,
    double? maxLon,
  }) {
    if (minLat == null || maxLat == null || minLon == null || maxLon == null) {
      return zones;
    }

    return zones
        .where((SafetyZone zone) {
          return zone.latitude >= minLat &&
              zone.latitude <= maxLat &&
              zone.longitude >= minLon &&
              zone.longitude <= maxLon;
        })
        .toList(growable: false);
  }

  Map<String, dynamic>? _coerceMap(Object? value) =>
      api_utils.coerceMap(value);

  List<LatLng> _polygonPoints(Object? coordinates) {
    if (coordinates is! List || coordinates.isEmpty) {
      return const <LatLng>[];
    }

    final Object? firstRingRaw = coordinates.first;
    if (firstRingRaw is! List || firstRingRaw.isEmpty) {
      return const <LatLng>[];
    }

    final List<LatLng> points = <LatLng>[];
    for (final dynamic point in firstRingRaw) {
      if (point is! List || point.length < 2) {
        continue;
      }

      final double? lon = _asDouble(point[0]);
      final double? lat = _asDouble(point[1]);
      if (lat == null || lon == null) {
        continue;
      }
      points.add(LatLng(lat, lon));
    }
    return points;
  }

  List<double>? _polygonCentroid(List<LatLng> points) {
    if (points.isEmpty) {
      return null;
    }

    double totalLat = 0;
    double totalLon = 0;
    for (final LatLng point in points) {
      totalLat += point.latitude;
      totalLon += point.longitude;
    }

    return <double>[totalLat / points.length, totalLon / points.length];
  }

  double? _asDouble(Object? value) => api_utils.asDouble(value);

  _Bounds? _boundsFromPoints(
    List<LatLng> points, {
    required double paddingDegrees,
  }) {
    if (points.isEmpty) {
      return null;
    }

    double minLat = points.first.latitude;
    double maxLat = points.first.latitude;
    double minLon = points.first.longitude;
    double maxLon = points.first.longitude;

    for (final LatLng point in points.skip(1)) {
      if (point.latitude < minLat) {
        minLat = point.latitude;
      }
      if (point.latitude > maxLat) {
        maxLat = point.latitude;
      }
      if (point.longitude < minLon) {
        minLon = point.longitude;
      }
      if (point.longitude > maxLon) {
        maxLon = point.longitude;
      }
    }

    return _Bounds(
      minLat: minLat - paddingDegrees,
      maxLat: maxLat + paddingDegrees,
      minLon: minLon - paddingDegrees,
      maxLon: maxLon + paddingDegrees,
    );
  }

  double _safetyScoreFromRisk(double riskScore) {
    final double normalizedRisk = riskScore <= 1 ? riskScore * 100 : riskScore;
    return (100 - normalizedRisk).clamp(0, 100).toDouble();
  }

  double _radiusMetersForRisk(double riskScore, String classification) {
    final double normalizedRisk = riskScore <= 1 ? riskScore * 100 : riskScore;
    if (classification == 'RISKY' || normalizedRisk >= 70) {
      return 180;
    }
    if (classification == 'CAUTIOUS' || normalizedRisk >= 40) {
      return 145;
    }
    return 115;
  }

  String _normalizeClassification(String? riskLevel, double riskScore) {
    final String normalized = (riskLevel ?? '').trim().toUpperCase();
    if (normalized == 'SAFE' ||
        normalized == 'CAUTIOUS' ||
        normalized == 'RISKY') {
      return normalized;
    }

    final double normalizedRisk = riskScore <= 1 ? riskScore * 100 : riskScore;
    if (normalizedRisk >= 70) {
      return 'RISKY';
    }
    if (normalizedRisk >= 40) {
      return 'CAUTIOUS';
    }
    return 'SAFE';
  }
}

class _Bounds {
  const _Bounds({
    required this.minLat,
    required this.maxLat,
    required this.minLon,
    required this.maxLon,
  });

  final double minLat;
  final double maxLat;
  final double minLon;
  final double maxLon;
}
