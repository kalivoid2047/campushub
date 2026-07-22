import 'package:flutter/material.dart';

/// Reusable status chip (pending sync, late, graded, etc.) per
/// docs/07-ui-ux.md §5. Always pairs color with text/icon, never color alone
/// (docs/07-ui-ux.md §10 accessibility requirement).
class StatusChip extends StatelessWidget {
  const StatusChip(
      {super.key, required this.label, required this.color, this.icon});

  final String label;
  final Color color;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: icon != null ? Icon(icon, size: 16) : null,
      label: Text(label),
      backgroundColor: color.withValues(alpha: 0.15),
    );
  }
}
