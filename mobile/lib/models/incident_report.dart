class IncidentReport {
  const IncidentReport({
    required this.id,
    required this.incidentType,
    required this.latitude,
    required this.longitude,
    required this.description,
    required this.createdAtIso,
  });

  final String id;
  final String incidentType;
  final double latitude;
  final double longitude;
  final String description;
  final String createdAtIso;

  factory IncidentReport.fromJson(Map<String, dynamic> json) {
    return IncidentReport(
      id: json['id'] as String,
      incidentType: json['incidentType'] as String,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      description: json['description'] as String,
      createdAtIso: json['createdAtIso'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'incidentType': incidentType,
      'latitude': latitude,
      'longitude': longitude,
      'description': description,
      'createdAtIso': createdAtIso,
    };
  }
}
