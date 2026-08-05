import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../domain/search_repository.dart';

/// Permission-scoped keyword search (docs/06 section 6, FR-SRCH-1). Debounces
/// input, then shows results grouped visually by kind with a tap-through to
/// the relevant screen where one exists (resources, message threads).
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _controller = TextEditingController();
  Timer? _debounce;
  SearchResults? _results;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String query) {
    _debounce?.cancel();
    final trimmed = query.trim();
    if (trimmed.length < 2) {
      setState(() {
        _results = null;
        _error = null;
      });
      return;
    }
    _debounce =
        Timer(const Duration(milliseconds: 350), () => _runSearch(trimmed));
  }

  Future<void> _runSearch(String query) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await ref.read(searchRepositoryProvider).search(query);
      if (mounted) setState(() => _results = results);
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openHit(SearchHit hit) {
    switch (hit.kind) {
      case 'resource':
        if (hit.contextId != null) {
          context.push('/modules/${hit.contextId}');
        }
      case 'message':
        if (hit.contextId != null) {
          context.push('/channels/${hit.contextId}', extra: 'Discussion');
        }
      default:
        showDialog<void>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(hit.title),
            content: Text(hit.snippet),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('Close'),
              ),
            ],
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Search resources, announcements, messages…',
            border: InputBorder.none,
          ),
          onChanged: _onChanged,
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
          child:
              Padding(padding: const EdgeInsets.all(24), child: Text(_error!)));
    }
    final results = _results;
    if (results == null) {
      return const Center(child: Text('Type at least 2 characters to search.'));
    }
    if (results.hits.isEmpty) {
      return const Center(child: Text('No results.'));
    }
    return Column(
      children: [
        if (results.truncated)
          Container(
            width: double.infinity,
            color: Theme.of(context).colorScheme.secondaryContainer,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Text(
              'Showing the first matches in each category — refine your '
              'search to narrow the results.',
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSecondaryContainer,
              ),
            ),
          ),
        Expanded(
          child: ListView.builder(
            itemCount: results.hits.length,
            itemBuilder: (context, index) {
              final hit = results.hits[index];
              return ListTile(
                leading: Icon(_iconFor(hit.kind)),
                title: Text(hit.title),
                subtitle: Text(hit.snippet,
                    maxLines: 2, overflow: TextOverflow.ellipsis),
                onTap: () => _openHit(hit),
              );
            },
          ),
        ),
      ],
    );
  }
}

IconData _iconFor(String kind) => switch (kind) {
      'resource' => Icons.description_outlined,
      'announcement' => Icons.campaign_outlined,
      'message' => Icons.chat_bubble_outline,
      _ => Icons.search,
    };
