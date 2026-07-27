"""
Test suite for FDF contact field extraction (author/maintainer).
"""

import json

import pytest

from ckanext.fair3r.lib.fdf.converter import FDFConverter, fdf_json_to_ckan_dataset


class TestFDFConverterContactFields:
    """Test extracting author/maintainer from FDF data"""

    def test_extract_by_role_first_author_first_maintainer(self):
        """Role-aware mapping: first Author -> author, first DataManager -> maintainer."""
        fdf_data = {
            "creators": [
                {
                    "givenName": "Alice",
                    "familyName": "Author",
                    "email": "alice@example.com",
                    "role": "Researcher",
                },
                {
                    "givenName": "Bob",
                    "familyName": "Maint",
                    "email": "bob@example.com",
                    "role": "DataManager",
                },
                {
                    "givenName": "Carol",
                    "familyName": "Maint",
                    "email": "carol@example.com",
                    "role": "DataManager",
                },
            ],
        }

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "Alice Author"
        assert result["author_email"] == "alice@example.com"
        assert result["maintainer"] == "Bob Maint"
        assert result["maintainer_email"] == "bob@example.com"

    def test_extract_single_creator_as_author(self):
        """Test extracting first creator as author"""
        fdf_data = {
            "creators": [
                {
                    "givenName": "Jane",
                    "familyName": "Smith",
                    "email": "jane.smith@example.com",
                }
            ]
        }

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "Jane Smith"
        assert result["author_email"] == "jane.smith@example.com"
        assert "maintainer" not in result
        assert "maintainer_email" not in result

    def test_extract_two_creators_without_maintainer_role(self):
        """Without explicit maintainer role, only author fields are filled."""
        fdf_data = {
            "creators": [
                {
                    "givenName": "Alice",
                    "familyName": "Anderson",
                    "email": "alice@example.com",
                },
                {"givenName": "Bob", "familyName": "Brown", "email": "bob@example.com"},
            ]
        }

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "Alice Anderson"
        assert result["author_email"] == "alice@example.com"
        assert "maintainer" not in result
        assert "maintainer_email" not in result

    def test_extract_multiple_creators_without_maintainer_role(self):
        """Without explicit maintainer role, additional creators stay as authors."""
        fdf_data = {
            "creators": [
                {
                    "givenName": "Alice",
                    "familyName": "Anderson",
                    "email": "alice@example.com",
                },
                {"givenName": "Bob", "familyName": "Brown", "email": "bob@example.com"},
                {
                    "givenName": "Carol",
                    "familyName": "Clark",
                    "email": "carol@example.com",
                },
            ]
        }

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "Alice Anderson"
        assert result["author_email"] == "alice@example.com"
        assert "maintainer" not in result
        assert "maintainer_email" not in result

    def test_creator_without_email(self):
        """Test creator with name but no email"""
        fdf_data = {"creators": [{"givenName": "John", "familyName": "Doe"}]}

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "John Doe"
        assert "author_email" not in result

    def test_creator_with_only_given_name(self):
        """Test creator with only given name, no family name"""
        fdf_data = {
            "creators": [{"givenName": "Madonna", "email": "madonna@example.com"}]
        }

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert result["author"] == "Madonna"
        assert result["author_email"] == "madonna@example.com"

    def test_empty_creators_list(self):
        """Test empty creators list"""
        fdf_data = {"creators": []}

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        # Should return empty dict, no author/maintainer
        assert "author" not in result
        assert "maintainer" not in result

    def test_no_creators_field(self):
        """Test missing creators field"""
        fdf_data = {}

        result = FDFConverter.convert_to_ckan_dataset(fdf_data)

        assert "author" not in result
        assert "maintainer" not in result

    def test_json_string_conversion(self):
        """Test converting from JSON string"""
        fdf_json = json.dumps(
            {
                "creators": [
                    {
                        "givenName": "Test",
                        "familyName": "User",
                        "email": "test@example.com",
                    }
                ]
            }
        )

        result = fdf_json_to_ckan_dataset(fdf_json)

        assert result["author"] == "Test User"
        assert result["author_email"] == "test@example.com"

    def test_invalid_json_raises_error(self):
        """Test handling of invalid JSON"""
        with pytest.raises(ValueError, match="Invalid FDF JSON"):
            fdf_json_to_ckan_dataset("{invalid json")

    def test_make_safe_name(self):
        """Test dataset name safety conversion"""
        test_cases = [
            ("My Dataset", "my-dataset"),
            ("Dataset-With-Hyphens", "dataset-with-hyphens"),
            ("Dataset_With_Underscores", "dataset-with-underscores"),
            ("Dataset@With#Special$Chars", "datasetwithspecialchars"),
            ("UPPERCASE Dataset", "uppercase-dataset"),
            ("  Leading and trailing spaces  ", "leading-and-trailing-spaces"),
            ("A" * 150, "a" * 100),  # Truncate to 100
        ]

        for title, expected in test_cases:
            result = FDFConverter._make_safe_name(title)
            assert result == expected, f"Failed for '{title}': got '{result}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
