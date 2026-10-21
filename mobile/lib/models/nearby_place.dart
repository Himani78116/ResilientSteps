import 'package:latlong2/latlong.dart';

enum NearbyCategory {
  hospital('hospital', 'Hospitals near me', 'Hospital', 'local_hospital'),
  police('police', 'Police stations', 'Police station', 'local_police'),
  metro('metro', 'Metro stations', 'Metro station', 'subway'),
  bus('bus', 'Bus stands', 'Bus stand', 'directions_bus');

  const NearbyCategory(this.code, this.label, this.shortLabel, this.iconName);

  final String code;
  final String label;
  final String shortLabel;
  final String iconName;

  static NearbyCategory? fromCode(String value) {
    for (final NearbyCategory category in values) {
      if (category.code == value) return category;
    }
    return null;
  }
}

class NearbyPlace {
  const NearbyPlace({
    required this.id,
    required this.name,
    required this.category,
    required this.latitude,
    required this.longitude,
    required this.distanceMeters,
    this.address,
  });

  final String id;
  final String name;
  final NearbyCategory category;
  final double latitude;
  final double longitude;
  final int distanceMeters;
  final String? address;

  LatLng get point => LatLng(latitude, longitude);

  factory NearbyPlace.fromJson(Map<String, dynamic> json) {
    double number(Object? value) =>
        value is num ? value.toDouble() : double.tryParse('$value') ?? 0;
    final NearbyCategory category =
        NearbyCategory.fromCode(json['category']?.toString() ?? '') ??
        NearbyCategory.hospital;
    return NearbyPlace(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? category.shortLabel,
      category: category,
      latitude: number(json['latitude']),
      longitude: number(json['longitude']),
      distanceMeters: number(json['distance_m']).round(),
      address: json['address']?.toString(),
    );
  }
}
