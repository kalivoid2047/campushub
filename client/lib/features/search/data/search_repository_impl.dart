import '../../../core/network/api_client.dart';
import '../domain/search_repository.dart';

class SearchRepositoryImpl implements SearchRepository {
  SearchRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<SearchResults> search(String query) async {
    final json = await _api.getJson('/api/v1/search', query: {'q': query});
    return SearchResults.fromJson(json);
  }
}
