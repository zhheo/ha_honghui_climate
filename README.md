# Honghui Climate Home Assistant Integration

English | [简体中文](docs/README_zh.md)

This is a Home Assistant custom integration that creates a virtual climate device. The device uses an existing climate entity for control and a separate temperature sensor entity to display the current temperature.

## Features

- Allows users to select existing climate entities and temperature sensor entities
- Creates a virtual climate device that inherits all functionalities from the source climate
- Uses a separate temperature sensor to display the current temperature
- All control commands are passed to the source climate entity

## Installation

1. Copy the `custom_components/honghui_climate` folder to the `custom_components` directory in your Home Assistant installation
   ```
   # For example, if you're using HASS.IO:
   /config/custom_components/honghui_climate
   ```
2. Restart Home Assistant
3. Go to the Integrations page in Home Assistant and click the "Add Integration" button
4. Search for "Honghui Climate" and select it
5. Follow the configuration flow

## Configuration

1. Select an existing climate entity in the configuration flow
2. Select an existing temperature sensor entity
3. After saving the configuration, a new virtual climate entity will be created

## Use Cases

- When the temperature sensor built into the AC is inaccurate
- When you need to use a temperature sensor located in a different position to control the AC
- To create more precise air conditioning control logic

## Available Services

The integration provides two services:

- `honghui_climate.set_ac_entity`: Update the climate entity used by the virtual climate
- `honghui_climate.set_temp_entity`: Update the temperature sensor entity used by the virtual climate

## Notes

- The source climate entity must be a valid climate type entity
- The temperature sensor must provide valid temperature data
- The functionality of the virtual climate depends on the functionality of the source climate

## Troubleshooting

If you can't find the entity after installation, try the following steps:

1. Check the Home Assistant logs for error messages
2. Make sure you have correctly selected the climate entity and temperature sensor entity in the configuration flow
3. Restart Home Assistant
4. If the problem persists, try removing the integration and reinstalling it 