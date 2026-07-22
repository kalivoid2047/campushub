import '../../../core/network/api_client.dart';
import '../domain/search_repository.dart';

class SearchRepositoryImpl implements SearchRepository {
  SearchRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<List<SearchHit>> search(String query) async {
    final json = await _api.getJson('/api/v1/search', query: {'q': query});
    return [
      for (final row in json['hits'] as List<dynamic>)
        SearchHit.fromJson(row as Map<String, dynamic>)
    ];
  }
}
