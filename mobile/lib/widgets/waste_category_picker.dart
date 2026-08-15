import 'package:flutter/material.dart';

import '../services/waste_reporting_api_service.dart';

class WasteCategoryPicker extends StatelessWidget {
  const WasteCategoryPicker({
    super.key,
    required this.categories,
    required this.selectedCategoryCode,
    required this.onCategorySelected,
  });

  final List<WasteCategory> categories;
  final String? selectedCategoryCode;
  final ValueChanged<String> onCategorySelected;

  IconData _getCategoryIcon(String code) {
    switch (code.toLowerCase()) {
      case 'overflowing_bin':
        return Icons.delete_sweep_outlined;
      case 'illegal_dumping':
        return Icons.warning_amber_rounded;
      case 'construction_debris':
        return Icons.foundation;
      case 'garbage_burning':
        return Icons.local_fire_department_outlined;
      case 'dead_animal':
        return Icons.pets_outlined;
      default:
        return Icons.cleaning_services_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: categories.map((WasteCategory category) {
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
