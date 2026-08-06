/// Search domain (client side of Epic E7, FR-SRCH-1).
library;

class SearchHit {
  const SearchHit({
    required this.kind,
    required this.id,
    required this.title,
    required this.snippet,
    required this.contextId,
    required this.createdAt,
  });

  final String kind; // "resource" | "announcement" | "message"
  final String id;
  final String title;
  final String snippet;
  final String? contextId; // module_id / scope_id / channel_id, per kind
  final DateTime createdAt;

  factory SearchHit.fromJson(Map<String, dynamic> json) => SearchHit(
        kind: json['kind'] as String,
        id: json['id'] as String,
        title: json['title'] as String,
        snippet: json['snippet'] as String,
        contextId: json['context_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class SearchResults {
  const SearchResults({required this.hits, required this.truncated});

  final List<SearchHit> hits;

  /// True when at least one kind hit its per-kind cap server-side — there
  /// may be more matches than [hits] shows; the UI should prompt the user
  /// to narrow the query rather than imply this is everything.
  final bool truncated;

  factory SearchResults.fromJson(Map<String, dynamic> json) => SearchResults(
        hits: [
          for (final row in json['hits'] as List<dynamic>)
            SearchHit.fromJson(row as Map<String, dynamic>)
        ],
        truncated: json['truncated'] as bool? ?? false,
      );
}

abstract class SearchRepository {
  /// Permission-scoped keyword search across resources, announcements, and
  /// messages (docs/06 section 6). Requires connectivity — search results
  /// are not cached (docs/09 does not list search among cached reads).
  Future<SearchResults> search(String query);
}
