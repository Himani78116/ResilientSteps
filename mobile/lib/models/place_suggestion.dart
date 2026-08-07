import 'package:latlong2/latlong.dart';

class PlaceSuggestion {
  const PlaceSuggestion({
    required this.title,
    required this.subtitle,
    required this.latitude,
    required this.longitude,
  });

  final String title;
  final String subtitle;
  final double latitude;
  final double longitude;

  LatLng get point => LatLng(latitude, longitude);

  factory PlaceSuggestion.fromJson(Map<String, dynamic> json) {
    double parseDouble(Object? value) {
      if (value is num) {
        return value.toDouble();
      }
      if (value is String) {
        return double.tryParse(value) ?? 0;
      }
      return 0;
    }

    final String displayName = json['display_name']?.toString().trim() ?? '';
    final List<String> parts = displayName
        .split(',')
        .map((String part) => part.trim())
        .where((String part) => part.isNotEmpty)
        .toList(growable: false);

    final String title = parts.isNotEmpty
        ? parts.first
        : (json['name']?.toString().trim().isNotEmpty ?? false)
        ? json['name'].toString().trim()
        : 'Pinned destination';
    final String subtitle = parts.length > 1
        ? parts.skip(1).take(3).join(', ')
        : 'Pune';

    return PlaceSuggestion(
      title: title,
      subtitle: subtitle,
      latitude: parseDouble(json['lat']),
      longitude: parseDouble(json['lon']),
    );
  }
}
