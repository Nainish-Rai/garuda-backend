import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from geopy.distance import geodesic
import os

class DataService:
    """Service for handling Census, socioeconomic, and real estate data"""

    def __init__(self):
        self.data_dir = "data"
        self.census_data = None
        self.real_estate_data = None
        self.geographic_mapping = None
        self._load_datasets()

    def _load_datasets(self):
        """Load all datasets into memory"""
        try:
            self.census_data = pd.read_csv(os.path.join(self.data_dir, "census_data.csv"))
            self.real_estate_data = pd.read_csv(os.path.join(self.data_dir, "real_estate_data.csv"))
            self.geographic_mapping = pd.read_csv(os.path.join(self.data_dir, "geographic_mapping.csv"))
            print("Datasets loaded successfully")
        except Exception as e:
            print(f"Error loading datasets: {e}")

    def get_zip_code_from_coordinates(self, lat: float, lon: float, max_distance_km: float = 10) -> Optional[str]:
        """Find the closest ZIP code to given coordinates"""
        if self.geographic_mapping is None:
            return None

        min_distance = float('inf')
        closest_zip = None

        for _, row in self.geographic_mapping.iterrows():
            distance = geodesic((lat, lon), (row['latitude'], row['longitude'])).kilometers
            if distance < min_distance and distance <= max_distance_km:
                min_distance = distance
                closest_zip = str(row['zip_code'])

        return closest_zip

    def get_zip_code_from_location(self, location_name: str) -> Optional[str]:
        """Get ZIP code from city name"""
        if self.geographic_mapping is None:
            return None

        # Try exact match first
        match = self.geographic_mapping[
            self.geographic_mapping['city'].str.lower() == location_name.lower()
        ]

        if not match.empty:
            return str(match.iloc[0]['zip_code'])

        # Try partial match
        match = self.geographic_mapping[
            self.geographic_mapping['city'].str.lower().str.contains(location_name.lower(), na=False)
        ]

        if not match.empty:
            return str(match.iloc[0]['zip_code'])

        return None

    def get_census_data(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """Get census and demographic data for a ZIP code"""
        if self.census_data is None:
            return None

        data = self.census_data[self.census_data['zip_code'] == int(zip_code)]
        if data.empty:
            return None

        return data.iloc[0].to_dict()

    def get_real_estate_data(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """Get real estate market data for a ZIP code"""
        if self.real_estate_data is None:
            return None

        data = self.real_estate_data[self.real_estate_data['zip_code'] == int(zip_code)]
        if data.empty:
            return None

        return data.iloc[0].to_dict()

    def get_comprehensive_analysis(self, lat: float, lon: float, location_name: str = None) -> Dict[str, Any]:
        """Get comprehensive socioeconomic and real estate analysis for a location"""

        # Try to get ZIP code from coordinates first, then from location name
        zip_code = self.get_zip_code_from_coordinates(lat, lon)
        if not zip_code and location_name:
            zip_code = self.get_zip_code_from_location(location_name)

        if not zip_code:
            return {
                "error": "No data available for this location",
                "zip_code": None,
                "census_data": None,
                "real_estate_data": None,
                "analysis": None
            }

        census_data = self.get_census_data(zip_code)
        real_estate_data = self.get_real_estate_data(zip_code)

        # Generate analysis insights
        analysis = self._generate_analysis(census_data, real_estate_data)

        return {
            "zip_code": zip_code,
            "census_data": census_data,
            "real_estate_data": real_estate_data,
            "analysis": analysis
        }

    def _generate_analysis(self, census_data: Dict, real_estate_data: Dict) -> Dict[str, Any]:
        """Generate analytical insights from the data"""
        if not census_data or not real_estate_data:
            return {"error": "Insufficient data for analysis"}

        analysis = {
            "socioeconomic_status": self._assess_socioeconomic_status(census_data),
            "housing_market": self._assess_housing_market(real_estate_data),
            "development_potential": self._assess_development_potential(census_data, real_estate_data),
            "change_indicators": self._assess_change_indicators(census_data, real_estate_data)
        }

        return analysis

    def _assess_socioeconomic_status(self, data: Dict) -> str:
        """Assess socioeconomic status based on census data"""
        income = data.get('median_income', 0)
        education = data.get('education_bachelor_plus', 0)
        poverty = data.get('poverty_rate', 0)

        if income > 100000 and education > 70 and poverty < 10:
            return "High socioeconomic status"
        elif income > 70000 and education > 50 and poverty < 15:
            return "Upper-middle socioeconomic status"
        elif income > 50000 and education > 30 and poverty < 20:
            return "Middle socioeconomic status"
        else:
            return "Lower socioeconomic status"

    def _assess_housing_market(self, data: Dict) -> str:
        """Assess housing market conditions"""
        price = data.get('avg_home_price', 0)
        inventory = data.get('inventory_months', 0)
        permits = data.get('new_construction_permits', 0)

        if inventory < 2 and permits > 20:
            return "Hot market with high development activity"
        elif inventory < 3 and price > 800000:
            return "Competitive high-value market"
        elif inventory > 4 and permits < 15:
            return "Slow market with limited development"
        else:
            return "Balanced market conditions"

    def _assess_development_potential(self, census_data: Dict, real_estate_data: Dict) -> str:
        """Assess potential for urban development"""
        permits = real_estate_data.get('new_construction_permits', 0)
        vacancy = real_estate_data.get('commercial_vacancy_rate', 0)
        population = census_data.get('population', 0)

        if permits > 30 and vacancy < 10:
            return "High development potential"
        elif permits > 15 and population > 20000:
            return "Moderate development potential"
        else:
            return "Low development potential"

    def _assess_change_indicators(self, census_data: Dict, real_estate_data: Dict) -> Dict[str, Any]:
        """Identify indicators that might correlate with satellite-detected changes"""
        indicators = {
            "gentrification_risk": "Low",
            "development_pressure": "Low",
            "economic_growth": "Stable"
        }

        # Gentrification indicators
        income = census_data.get('median_income', 0)
        home_value = census_data.get('median_home_value', 0)
        education = census_data.get('education_bachelor_plus', 0)

        if income > 80000 and home_value > 600000 and education > 60:
            indicators["gentrification_risk"] = "High"
        elif income > 60000 and home_value > 400000:
            indicators["gentrification_risk"] = "Moderate"

        # Development pressure
        permits = real_estate_data.get('new_construction_permits', 0)
        days_on_market = real_estate_data.get('days_on_market', 0)

        if permits > 25 and days_on_market < 35:
            indicators["development_pressure"] = "High"
        elif permits > 15:
            indicators["development_pressure"] = "Moderate"

        # Economic growth
        rent_growth = real_estate_data.get('rent_growth_yoy', 0)
        unemployment = census_data.get('unemployment_rate', 0)

        if rent_growth > 5 and unemployment < 4:
            indicators["economic_growth"] = "Strong"
        elif rent_growth > 3:
            indicators["economic_growth"] = "Moderate"

        return indicators

# Global instance
data_service = DataService()