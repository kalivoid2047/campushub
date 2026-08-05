import '../../../core/network/api_client.dart';
import '../domain/portfolio_repository.dart';

class PortfolioRepositoryImpl implements PortfolioRepository {
  PortfolioRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<Portfolio> myPortfolio() async {
    final json = await _api.getJson('/api/v1/portfolio/me');
    return Portfolio.fromJson(json);
  }
}
