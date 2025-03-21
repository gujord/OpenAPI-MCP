import axios from 'axios';

interface WeatherData {
  temperature: number;
  windSpeed: number;
  precipitation: number;
}

class WeatherService {
  private readonly baseUrl = 'https://api.met.no/weatherapi/locationforecast/2.0';
  
  async getWeather(latitude: number, longitude: number): Promise<WeatherData> {
    try {
      const response = await axios.get(`${this.baseUrl}/compact`, {
        params: {
          lat: latitude,
          lon: longitude
        },
        headers: {
          'User-Agent': 'MinVærApp/1.0 (din@epost.no)'
        }
      });

      const currentData = response.data.properties.timeseries[0].data.instant.details;
      
      return {
        temperature: currentData.air_temperature,
        windSpeed: currentData.wind_speed,
        precipitation: currentData.precipitation_amount
      };
    } catch (error) {
      throw new Error('Kunne ikke hente værdata: ' + error.message);
    }
  }
}

// Asker koordinater (omtrentlig)
const ASKER_LAT = 59.8325;
const ASKER_LON = 10.4347; 