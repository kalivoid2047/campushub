import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../domain/portfolio_repository.dart';

/// The caller's own academic portfolio (FR-PORT-1, Epic E10): completed
/// courses, grades, and graded work — self-service only, no roster.
class PortfolioScreen extends ConsumerStatefulWidget {
  const PortfolioScreen({super.key});

  @override
  ConsumerState<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends ConsumerState<PortfolioScreen> {
  late Future<Portfolio> _future;

  @override
  void initState() {
    super.initState();
    _future = ref.read(portfolioRepositoryProvider).myPortfolio();
  }

  Future<void> _refresh() async {
    final next = ref.read(portfolioRepositoryProvider).myPortfolio();
    setState(() => _future = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Portfolio')),
      body: FutureBuilder<Portfolio>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('${snapshot.error}', textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    OutlinedButton(
                        onPressed: _refresh, child: const Text('Retry')),
                  ],
                ),
              ),
            );
          }
          final portfolio = snapshot.data!;
          if (portfolio.courses.isEmpty) {
            return const Center(child: Text('No enrolled courses yet.'));
          }
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: portfolio.courses.length,
              itemBuilder: (context, index) =>
                  _CourseCard(course: portfolio.courses[index]),
            ),
          );
        },
      ),
    );
  }
}

class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.course});

  final PortfolioCourseEntry course;

  @override
  Widget build(BuildContext context) {
    final average = course.averageScorePercent;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(course.courseName,
                          style: Theme.of(context).textTheme.titleMedium),
                      Text(
                        '${course.courseCode} • ${course.term} • ${course.departmentName}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                if (average != null)
                  Chip(label: Text('${average.toStringAsFixed(0)}%'))
                else
                  const Chip(label: Text('Not graded yet')),
              ],
            ),
            if (course.assignments.isNotEmpty) ...[
              const Divider(height: 20),
              for (final entry in course.assignments)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    children: [
                      Expanded(child: Text(entry.title)),
                      Text(
                        '${entry.score.toStringAsFixed(0)}/${entry.maxScore.toStringAsFixed(0)}',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
