import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../widgets/incident_modal.dart';

class ReportIncidentScreen extends StatelessWidget {
  const ReportIncidentScreen({super.key, required this.initialLocation});

  final LatLng initialLocation;

  @override
  Widget build(BuildContext context) {
    return Material(
      type: MaterialType.transparency,
      child: SafeArea(
        child: Center(
          child: IncidentModal(
            initialLocation: initialLocation,
            onClose: () => Navigator.of(context).pop(),
          ),
        ),
      ),
    );
  }
}
