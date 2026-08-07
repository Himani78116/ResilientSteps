import '../entities/risk.dart';

abstract class RiskRepository {
  Future<Risk> getRiskForLocation(double lat, double lon);
  Stream<Risk> watchRiskForCurrentLocation();
}
