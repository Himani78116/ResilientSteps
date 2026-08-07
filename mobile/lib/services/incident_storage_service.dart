import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/incident_report.dart';

class IncidentStorageService {
  static const String _reportsKey = 'walksafe_incident_reports';

  Future<List<IncidentReport>> getReports() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final List<String> rawReports =
        prefs.getStringList(_reportsKey) ?? <String>[];

    return rawReports
        .map(
          (String rawReport) => IncidentReport.fromJson(
            jsonDecode(rawReport) as Map<String, dynamic>,
          ),
        )
        .toList(growable: false);
  }

  Future<void> saveReport(IncidentReport report) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final List<IncidentReport> reports = await getReports();

    final List<IncidentReport> updatedReports = <IncidentReport>[
      ...reports,
      report,
    ];

    final List<String> serializedReports = updatedReports
        .map((IncidentReport item) => jsonEncode(item.toJson()))
        .toList(growable: false);

    await prefs.setStringList(_reportsKey, serializedReports);
  }
}
