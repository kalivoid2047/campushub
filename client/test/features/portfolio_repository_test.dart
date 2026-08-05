import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/features/portfolio/data/portfolio_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('myPortfolio parses courses, grades, and a null average', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/portfolio/me');
        return http.Response(
          jsonEncode({
            'user_id': 'u-1',
            'full_name': 'Ada Lovelace',
            'courses': [
              {
                'course_id': 'c-1',
                'course_name': 'Algorithms',
                'course_code': 'CS201',
                'term': '2026-S',
                'department_name': 'Comp Sci',
                'average_score_percent': 70.0,
                'assignments': [
                  {
                    'assignment_id': 'a-1',
                    'title': 'PS1',
                    'score': 90.0,
                    'max_score': 100.0,
                    'graded_at': '2026-07-16T00:00:00Z',
                  },
                ],
              },
              {
                'course_id': 'c-2',
                'course_name': 'Intro',
                'course_code': 'CS101',
                'term': '2026-S',
                'department_name': 'Comp Sci',
                'average_score_percent': null,
                'assignments': [],
              },
            ],
          }),
          200,
        );
      }),
    );
    final repository = PortfolioRepositoryImpl(api);

    final portfolio = await repository.myPortfolio();
    expect(portfolio.fullName, 'Ada Lovelace');
    expect(portfolio.courses, hasLength(2));
    expect(portfolio.courses[0].averageScorePercent, 70.0);
    expect(portfolio.courses[0].assignments.single.title, 'PS1');
    expect(portfolio.courses[1].averageScorePercent, isNull);
    expect(portfolio.courses[1].assignments, isEmpty);
  });
}
