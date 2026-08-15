import 'package:flutter/material.dart';

import '../services/infra_reporting_api_service.dart';

class InfraCategoryPicker extends StatelessWidget {
  const InfraCategoryPicker({
    super.key,
    required this.categories,
    required this.selectedCategoryCode,
    required this.onCategorySelected,
  });

  final List<InfraCategory> categories;
  final String? selectedCategoryCode;
  final ValueChanged<String> onCategorySelected;

  IconData _getCategoryIcon(String code) {
    switch (code.toLowerCase()) {
      case 'pothole':
        return Icons.warning_amber_rounded;
      case 'streetlight':
        return Icons.lightbulb_outline;
      case 'footpath':
        return Icons.directions_walk;
      case 'fallen_tree':
        return Icons.nature;
      case 'traffic_signal':
        return Icons.traffic;
      case 'water_leak':
        return Icons.water_drop_outlined;
      case 'waterlogging':
        return Icons.pool;
      case 'obstruction':
        return Icons.block;
      default:
        return Icons.build;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: categories.map((InfraCategory category) {
        final bool isSelected = category.code == selectedCategoryCode;
        return ChoiceChip(
          avatar: Icon(
            _getCategoryIcon(category.code),
            size: 18,
            color: isSelected ? Colors.white : Theme.of(context).primaryColor,
          ),
          label: Text(category.label),
          selected: isSelected,
          selectedColor: Theme.of(context).primaryColor,
          labelStyle: TextStyle(
            color: isSelected ? Colors.white : Colors.black87,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
          onSelected: (bool selected) {
            if (selected) {
              onCategorySelected(category.code);
            }
          },
        );
      }).toList(),
    );
  }
}
