"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

import pytest

from homeassistant.components.homekit.accessories import (
    debounce, HomeAccessory, HomeBridge, HomeDriver)
from homeassistant.components.homekit.const import (
    BRIDGE_MODEL, BRIDGE_NAME, BRIDGE_SERIAL_NUMBER, CHAR_FIRMWARE_REVISION,
    CHAR_MANUFACTURER, CHAR_MODEL, CHAR_NAME, CHAR_SERIAL_NUMBER,
    MANUFACTURER, SERV_ACCESSORY_INFO)
from homeassistant.const import __version__, ATTR_NOW, EVENT_TIME_CHANGED
import homeassistant.util.dt as dt_util


async def test_debounce(hass):
    """Test add_timeout decorator function."""
    def demo_func(*args):
        nonlocal arguments, counter
        counter += 1
        arguments = args

    arguments = None
    counter = 0
    mock = Mock(hass=hass, debounce={})

    debounce_demo = debounce(demo_func)
    assert debounce_demo.__name__ == 'demo_func'
    now = datetime(2018, 1, 1, 20, 0, 0, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        await hass.async_add_job(debounce_demo, mock, 'value')
    hass.bus.async_fire(
        EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 1
    assert len(arguments) == 2

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        await hass.async_add_job(debounce_demo, mock, 'value')
        await hass.async_add_job(debounce_demo, mock, 'value')

    hass.bus.async_fire(
        EVENT_TIME_CHANGED, {ATTR_NOW: now + timedelta(seconds=3)})
    await hass.async_block_till_done()
    assert counter == 2


async def test_home_accessory(hass, hk_driver):
    """Test HomeAccessory class."""
    entity_id = 'homekit.accessory'
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = HomeAccessory(hass, hk_driver, 'Home Accessory',
                        entity_id, 2, None)
    assert acc.hass == hass
    assert acc.display_name == 'Home Accessory'
    assert acc.aid == 2
    assert acc.category == 1  # Category.OTHER
    assert len(acc.services) == 1
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == 'Home Accessory'
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == 'Homekit'
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == \
        'homekit.accessory'

    hass.states.async_set(entity_id, 'on')
    await hass.async_block_till_done()
    with patch('homeassistant.components.homekit.accessories.'
               'HomeAccessory.update_state') as mock_update_state:
        await hass.async_add_job(acc.run)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        mock_update_state.assert_called_with(state)

        hass.states.async_remove(entity_id)
        await hass.async_block_till_done()
        assert mock_update_state.call_count == 1

    with pytest.raises(NotImplementedError):
        acc.update_state('new_state')

    # Test model name from domain
    entity_id = 'test_model.demo'
    acc = HomeAccessory('hass', hk_driver, 'test_name', entity_id, 2, None)
    serv = acc.services[0]  # SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_MODEL).value == 'Test Model'


def test_home_bridge(hk_driver):
    """Test HomeBridge class."""
    bridge = HomeBridge('hass', hk_driver)
    assert bridge.hass == 'hass'
    assert bridge.display_name == BRIDGE_NAME
    assert bridge.category == 2  # Category.BRIDGE
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO
    assert serv.display_name == SERV_ACCESSORY_INFO
    assert serv.get_characteristic(CHAR_NAME).value == BRIDGE_NAME
    assert serv.get_characteristic(CHAR_FIRMWARE_REVISION).value == __version__
    assert serv.get_characteristic(CHAR_MANUFACTURER).value == MANUFACTURER
    assert serv.get_characteristic(CHAR_MODEL).value == BRIDGE_MODEL
    assert serv.get_characteristic(CHAR_SERIAL_NUMBER).value == \
        BRIDGE_SERIAL_NUMBER

    bridge = HomeBridge('hass', hk_driver, 'test_name')
    assert bridge.display_name == 'test_name'
    assert len(bridge.services) == 1
    serv = bridge.services[0]  # SERV_ACCESSORY_INFO

    # setup_message
    bridge.setup_message()


def test_home_driver():
    """Test HomeDriver class."""
    ip_address = '127.0.0.1'
    port = 51826
    path = '.homekit.state'
    pin = b'123-45-678'

    with patch('pyhap.accessory_driver.AccessoryDriver.__init__') \
            as mock_driver:
        driver = HomeDriver('hass', address=ip_address, port=port,
                            persist_file=path)

    mock_driver.assert_called_with(address=ip_address, port=port,
                                   persist_file=path)
    driver.state = Mock(pincode=pin)

    # pair
    with patch('pyhap.accessory_driver.AccessoryDriver.pair') as mock_pair, \
        patch('homeassistant.components.homekit.accessories.'
              'dismiss_setup_message') as mock_dissmiss_msg:
        driver.pair('client_uuid', 'client_public')

    mock_pair.assert_called_with('client_uuid', 'client_public')
    mock_dissmiss_msg.assert_called_with('hass')

    # unpair
    with patch('pyhap.accessory_driver.AccessoryDriver.unpair') \
        as mock_unpair, \
        patch('homeassistant.components.homekit.accessories.'
              'show_setup_message') as mock_show_msg:
        driver.unpair('client_uuid')

    mock_unpair.assert_called_with('client_uuid')
    mock_show_msg.assert_called_with('hass', pin)
