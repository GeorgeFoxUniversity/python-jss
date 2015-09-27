#!/usr/bin/env python
# Copyright (C) 2014, 2015 Shea G Craig <shea.craig@da.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""jssobjects.py

Classes representing JSS database objects and their API endpoints
"""


import mimetypes
import os
from xml.etree import ElementTree

import requests

from .exceptions import (JSSMethodNotAllowedError, JSSPostError,
                         JSSFileUploadParameterError, JSSGetError)
from .jssobject import (JSSContainerObject, JSSFlatObject,
                        JSSGroupObject, JSSDeviceObject)
from .tools import error_handler


# pylint: disable=missing-docstring
class Account(JSSContainerObject):
    """JSS account."""
    _url = "/accounts"
    container = "users"
    id_url = "/userid/"
    search_types = {"userid": "/userid/", "username": "/username/",
                    "name": "/username/"}


class AccountGroup(JSSContainerObject):
    """Account groups are groups of users on the JSS.

    Within the API hierarchy they are actually part of accounts, but I
    seperated them.
    """

    _url = "/accounts"
    container = "groups"
    id_url = "/groupid/"
    search_types = {"groupid": "/groupid/", "groupname": "/groupname/",
                    "name": "/groupname/"}


class ActivationCode(JSSFlatObject):
    _url = "/activationcode"
    list_type = "activation_code"
    can_delete = False
    can_post = False
    can_list = False


class AdvancedComputerSearch(JSSContainerObject):
    _url = "/advancedcomputersearches"


class AdvancedMobileDeviceSearch(JSSContainerObject):
    _url = "/advancedmobiledevicesearches"


class AdvancedUserSearch(JSSContainerObject):
    _url = "/advancedusersearches"


class Building(JSSContainerObject):
    _url = "/buildings"
    list_type = "building"


class BYOProfile(JSSContainerObject):
    _url = "/byoprofiles"
    list_type = "byoprofiles"
    can_delete = False
    can_post = False


class Category(JSSContainerObject):
    _url = "/categories"
    list_type = "category"


class Class(JSSContainerObject):
    _url = "/classes"


class Computer(JSSDeviceObject):
    list_type = "computer"
    _url = "/computers"
    search_types = {"name": "/name/", "serial_number": "/serialnumber/",
                    "udid": "/udid/", "macaddress": "/macadress/",
                    "match": "/match/"}

    @property
    def mac_addresses(self):
        """Return a list of mac addresses for this device.

        Computers don't tell you which network device is which.
        """
        mac_addresses = [self.findtext("general/mac_address")]
        if self.findtext("general/alt_mac_address"):
            mac_addresses.append(self.findtext("general/alt_mac_address"))
            return mac_addresses


class ComputerCheckIn(JSSFlatObject):
    _url = "/computercheckin"
    can_delete = False
    can_list = False
    can_post = False


class ComputerCommand(JSSContainerObject):
    _url = "/computercommands"
    can_delete = False
    can_put = False
    # TODO: You _can_ POST computer commands, but it is not yet
    # implemented
    can_post = False


class ComputerConfiguration(JSSContainerObject):
    _url = "/computerconfigurations"
    list_type = "computer_configuration"


class ComputerExtensionAttribute(JSSContainerObject):
    _url = "/computerextensionattributes"


class ComputerGroup(JSSGroupObject):
    _url = "/computergroups"
    list_type = "computer_group"

    def __init__(self, jss, data, **kwargs):
        """Init a ComputerGroup, adding in extra Elements."""
        # Temporary solution to #34.
        # When grabbing a ComputerGroup from the JSS, we don't get the
        # convenience properties for accessing some of the elements
        # that the new() method adds. For now, this just adds in a
        # criteria property. But...
        # TODO(Shea): Find a generic/higher level way to add these
        #   convenience accessors.
        super(ComputerGroup, self).__init__(jss, data, **kwargs)
        self.criteria = self.find("criteria")

    def new(self, name, **kwargs):
        """Create a computer group from scratch.

        Smart groups with no criteria by default select ALL computers.

        Args:
            name: String name of group.
            kwargs: One kwarg of "smart" is accepted, with bool val.
        """
        element_name = ElementTree.SubElement(self, "name")
        element_name.text = name
        # is_smart is a JSSGroupObject @property.
        ElementTree.SubElement(self, "is_smart")
        self.criteria = ElementTree.SubElement(self, "criteria")
        # If specified add is_smart, otherwise default to False.
        self.is_smart = kwargs.get("smart", False)
        self.computers = ElementTree.SubElement(self, "computers")

    def add_computer(self, computer):
        """Add a computer to the group.

        Args:
            computer: A Computer object to add to the group.
        """
        super(ComputerGroup, self).add_device(computer, "computers")

    def remove_computer(self, computer):
        """Remove a computer from the group.

        Args:
            computer: A Computer object to add to the group.
        """
        super(ComputerGroup, self).remove_object_from_list(computer, "computers")


class ComputerInventoryCollection(JSSFlatObject):
    _url = "/computerinventorycollection"
    can_list = False
    can_post = False
    can_delete = False


class ComputerInvitation(JSSContainerObject):
    _url = "/computerinvitations"
    can_put = False
    search_types = {"name": "/name/", "invitation": "/invitation/"}


class ComputerReport(JSSContainerObject):
    _url = "/computerreports"
    can_put = False
    can_post = False
    can_delete = False


class Department(JSSContainerObject):
    _url = "/departments"
    list_type = "department"


class DirectoryBinding(JSSContainerObject):
    _url = "/directorybindings"


class DiskEncryptionConfiguration(JSSContainerObject):
    _url = "/diskencryptionconfigurations"


class DistributionPoint(JSSContainerObject):
    _url = "/distributionpoints"


class DockItem(JSSContainerObject):
    _url = "/dockitems"


class EBook(JSSContainerObject):
    _url = "/ebooks"


class FileUpload(object):
    """FileUploads are a special case in the API. They allow you to add
    file resources to a number of objects on the JSS.

    To use, instantiate a new FileUpload object, then use the save()
    method to upload.

    Once the upload has been posted you may only interact with it
    through the web interface. You cannot list/get it or delete it
    through the API.

    However, you can reuse the FileUpload object if you wish, by
    changing the parameters, and issuing another save().
    """
    _url = "fileuploads"

    def __init__(self, j, resource_type, id_type, _id, resource):
        """Prepare a new FileUpload.

        Args:
            j: A JSS object to POST the upload to.
            resource_type:
                String. Acceptable Values:
                    Attachments:
                        computers
                        mobiledevices
                        enrollmentprofiles
                        peripherals
                    Icons:
                        policies
                        ebooks
                        mobiledeviceapplicationsicon
                    Mobile Device Application:
                        mobiledeviceapplicationsipa
                    Disk Encryption
                        diskencryptionconfigurations
            id_type:
                String of desired ID type:
                    id
                    name
            _id: Int or String referencing the identity value of the
                resource to add the FileUpload to.
            resource: String path to the file to upload.
        """
        resource_types = ["computers", "mobiledevices", "enrollmentprofiles",
                          "peripherals", "policies", "ebooks",
                          "mobiledeviceapplicationsicon",
                          "mobiledeviceapplicationsipa",
                          "diskencryptionconfigurations"]
        id_types = ["id", "name"]

        self.jss = j

        # Do some basic error checking on parameters.
        if resource_type in resource_types:
            self.resource_type = resource_type
        else:
            raise JSSFileUploadParameterError("resource_type must be one of: "
                                              "%s" % resource_types)
        if id_type in id_types:
            self.id_type = id_type
        else:
            raise JSSFileUploadParameterError("id_type must be one of: "
                                              "%s" % id_types)
        self._id = str(_id)

        basename = os.path.basename(resource)
        content_type = mimetypes.guess_type(basename)[0]
        self.resource = {"name": (basename, open(resource, "rb"),
                                  content_type)}
        self._set_upload_url()

    def _set_upload_url(self):
        """Generate the full URL for a POST."""
        # pylint: disable=protected-access
        self._upload_url = "/".join(
            [self.jss._url, self._url, self.resource_type, self.id_type,
             str(self._id)])
        # pylint: enable=protected-access

    def save(self):
        """POST the object to the JSS."""
        try:
            response = requests.post(self._upload_url,
                                     auth=self.jss.session.auth,
                                     verify=self.jss.session.verify,
                                     files=self.resource)
        except JSSPostError as error:
            if error.status_code == 409:
                raise JSSPostError(error)
            else:
                raise JSSMethodNotAllowedError(self.__class__.__name__)

        if response.status_code == 201:
            if self.jss.verbose:
                print "POST: Success"
                print response.text.encode("utf-8")
        elif response.status_code >= 400:
            error_handler(JSSPostError, response)


class GSXConnection(JSSFlatObject):
    _url = "/gsxconnection"
    can_list = False
    can_post = False
    can_delete = False


class IBeacon(JSSContainerObject):
    _url = "/ibeacons"
    list_type = "ibeacon"


class JSSUser(JSSFlatObject):
    """JSSUser is deprecated."""
    _url = "/jssuser"
    can_list = False
    can_post = False
    can_put = False
    can_delete = False
    search_types = {}


class LDAPServer(JSSContainerObject):
    _url = "/ldapservers"

    def search_users(self, user):
        """Search for LDAP users.

        Args:
            user: User to search for. It is not entirely clear how the
                JSS determines the results- are regexes allowed, or
                globbing?

        Returns:
            LDAPUsersResult object.

        Raises:
            Will raise a JSSGetError if no results are found.
        """
        user_url = "%s/%s/%s" % (self.url, "user", user)
        response = self.jss.get(user_url)
        return LDAPUsersResults(self.jss, response)

    def search_groups(self, group):
        """Search for LDAP groups.

        Args:
            group: Group to search for. It is not entirely clear how the
                JSS determines the results- are regexes allowed, or
                globbing?

        Returns:
            LDAPGroupsResult object.

        Raises:
            JSSGetError if no results are found.
        """
        group_url = "%s/%s/%s" % (self.url, "group", group)
        response = self.jss.get(group_url)
        return LDAPGroupsResults(self.jss, response)

    def is_user_in_group(self, user, group):
        """Test for whether a user is in a group.

        There is also the ability in the API to test for whether
        multiple users are members of an LDAP group, but you should just
        call is_user_in_group over an enumerated list of users.

        Args:
            user: String username.
            group: String group name.

        Returns bool.
        """
        search_url = "%s/%s/%s/%s/%s" % (self.url, "group", group,
                                         "user", user)
        response = self.jss.get(search_url)
        # Sanity check
        length = len(response)
        result = False
        if length == 1:
            # User doesn't exist. Use default False value.
            pass
        elif length == 2:
            if response.findtext("ldap_user/username") == user:
                if response.findtext("ldap_user/is_member") == "Yes":
                    result = True
        elif len(response) >= 2:
            raise JSSGetError("Unexpected response.")
        return result

    @property
    def id(self):
        """Return object ID or None."""
        # LDAPServer's ID is in "connection"
        result = self.findtext("connection/id")
        return result

    @property
    def name(self):
        """Return object name or None."""
        # LDAPServer's name is in "connection"
        result = self.findtext("connection/name")
        return result


class LDAPUsersResults(JSSContainerObject):
    """Helper class for results of LDAPServer queries for users."""
    can_get = False
    can_post = False
    can_put = False
    can_delete = False


class LDAPGroupsResults(JSSContainerObject):
    """Helper class for results of LDAPServer queries for groups."""
    can_get = False
    can_post = False
    can_put = False
    can_delete = False


class LicensedSoftware(JSSContainerObject):
    _url = "/licensedsoftware"


class MacApplication(JSSContainerObject):
    _url = "/macapplications"
    list_type = "mac_application"


class ManagedPreferenceProfile(JSSContainerObject):
    _url = "/managedpreferenceprofiles"


class MobileDevice(JSSDeviceObject):
    """Mobile Device objects include a "match" search type which queries
    across multiple properties.
    """

    _url = "/mobiledevices"
    list_type = "mobile_device"
    search_types = {"name": "/name/", "serial_number": "/serialnumber/",
                    "udid": "/udid/", "macaddress": "/macadress/",
                    "match": "/match/"}

    @property
    def wifi_mac_address(self):
        """Return device's WIFI MAC address or None."""
        return self.findtext("general/wifi_mac_address")

    @property
    def bluetooth_mac_address(self):
        """Return device's Bluetooth MAC address or None."""
        return self.findtext("general/bluetooth_mac_address") or \
            self.findtext("general/mac_address")


class MobileDeviceApplication(JSSContainerObject):
    _url = "/mobiledeviceapplications"


class MobileDeviceCommand(JSSContainerObject):
    _url = "/mobiledevicecommands"
    can_put = False
    can_delete = False
    search_types = {"name": "/name/", "uuid": "/uuid/",
                    "command": "/command/"}
    # TODO: This object _can_ post, but it works a little differently
    # and is not yet implemented
    can_post = False


class MobileDeviceConfigurationProfile(JSSContainerObject):
    _url = "/mobiledeviceconfigurationprofiles"


class MobileDeviceEnrollmentProfile(JSSContainerObject):
    _url = "/mobiledeviceenrollmentprofiles"
    search_types = {"name": "/name/", "invitation": "/invitation/"}


class MobileDeviceExtensionAttribute(JSSContainerObject):
    _url = "/mobiledeviceextensionattributes"


class MobileDeviceInvitation(JSSContainerObject):
    _url = "/mobiledeviceinvitations"
    can_put = False
    search_types = {"invitation": "/invitation/"}


class MobileDeviceGroup(JSSGroupObject):
    _url = "/mobiledevicegroups"
    list_type = "mobile_device_group"

    def add_mobile_device(self, device):
        """Add a mobile_device to the group.

        Args:
            device: A MobileDevice object to add to group.
        """
        super(MobileDeviceGroup, self).add_device(device, "mobile_devices")

    def remove_mobile_device(self, device):
        """Remove a mobile_device from the group.

        Args:
            device: A MobileDevice object to remove from the group.
        """
        super(MobileDeviceGroup, self).remove_object_from_list(
            device, "mobile_devices")


class MobileDeviceProvisioningProfile(JSSContainerObject):
    _url = "/mobiledeviceprovisioningprofiles"
    search_types = {"name": "/name/", "uuid": "/uuid/"}


class NetbootServer(JSSContainerObject):
    _url = "/netbootservers"


class NetworkSegment(JSSContainerObject):
    _url = "/networksegments"


class OSXConfigurationProfile(JSSContainerObject):
    _url = "/osxconfigurationprofiles"


class Package(JSSContainerObject):
    _url = "/packages"
    list_type = "package"

    def new(self, filename, **kwargs):
        """Create a new Package from scratch.

        Args:
            filename: String filename of the package to use for the
                Package object's Display Name (here, "name").
            kwargs:
                Accepted keyword args include:
                    cat_name: Name of category to assign Package.
        """
        name = ElementTree.SubElement(self, "name")
        name.text = filename
        category = ElementTree.SubElement(self, "category")
        category.text = kwargs.get("cat_name")
        fname = ElementTree.SubElement(self, "filename")
        fname.text = filename
        ElementTree.SubElement(self, "info")
        ElementTree.SubElement(self, "notes")
        priority = ElementTree.SubElement(self, "priority")
        priority.text = "10"
        reboot = ElementTree.SubElement(self, "reboot_required")
        reboot.text = "false"
        fut = ElementTree.SubElement(self, "fill_user_template")
        fut.text = "false"
        feu = ElementTree.SubElement(self, "fill_existing_users")
        feu.text = "false"
        boot_volume = ElementTree.SubElement(self, "boot_volume_required")
        boot_volume.text = "true"
        allow_uninstalled = ElementTree.SubElement(self, "allow_uninstalled")
        allow_uninstalled.text = "false"
        ElementTree.SubElement(self, "os_requirements")
        required_proc = ElementTree.SubElement(self, "required_processor")
        required_proc.text = "None"
        switch_w_package = ElementTree.SubElement(self, "switch_with_package")
        switch_w_package.text = "Do Not Install"
        install_if = ElementTree.SubElement(self,
                                            "install_if_reported_available")
        install_if.text = "false"
        reinstall_option = ElementTree.SubElement(self, "reinstall_option")
        reinstall_option.text = "Do Not Reinstall"
        ElementTree.SubElement(self, "triggering_files")
        send_notification = ElementTree.SubElement(self, "send_notification")
        send_notification.text = "false"

    def set_os_requirements(self, requirements):
        """Set package OS Requirements

        Args:
            requirements: A string of comma seperated OS versions. A
                lowercase "x" is allowed as a wildcard, e.g.  "10.9.x"
        """
        self.find("os_requirements").text = requirements

    def set_category(self, category):
        """Set package category

        Args:
            category: String of an existing category's name, or a
                Category object.
        """
        # For some reason, packages only have the category name, not the
        # ID.
        if isinstance(category, Category):
            name = category.name
        else:
            name = category
        self.find("category").text = name


class Peripheral(JSSContainerObject):
    _url = "/peripherals"
    search_types = {}


class PeripheralType(JSSContainerObject):
    _url = "/peripheraltypes"
    search_types = {}


class Policy(JSSContainerObject):
    _url = "/policies"
    list_type = "policy"

    def new(self, name="Unknown", category=None):
        """Create a Policy from scratch.

        Args:
            name: String Policy name
            category: A Category object or string name of the category.
        """
        # General
        self.general = ElementTree.SubElement(self, "general")
        self.name_element = ElementTree.SubElement(self.general, "name")
        self.name_element.text = name
        self.enabled = ElementTree.SubElement(self.general, "enabled")
        self.set_bool(self.enabled, True)
        self.frequency = ElementTree.SubElement(self.general, "frequency")
        self.frequency.text = "Once per computer"
        self.category = ElementTree.SubElement(self.general, "category")
        if category:
            self.category_name = ElementTree.SubElement(self.category, "name")
            if isinstance(category, Category):
                self.category_name.text = category.name
            elif isinstance(category, basestring):
                self.category_name.text = category

        # Scope
        self.scope = ElementTree.SubElement(self, "scope")
        self.computers = ElementTree.SubElement(self.scope, "computers")
        self.computer_groups = ElementTree.SubElement(self.scope,
                                                      "computer_groups")
        self.buildings = ElementTree.SubElement(self.scope, "buldings")
        self.departments = ElementTree.SubElement(self.scope, "departments")
        self.exclusions = ElementTree.SubElement(self.scope, "exclusions")
        self.excluded_computers = ElementTree.SubElement(self.exclusions,
                                                         "computers")
        self.excluded_computer_groups = ElementTree.SubElement(
            self.exclusions, "computer_groups")
        self.excluded_buildings = ElementTree.SubElement(
            self.exclusions, "buildings")
        self.excluded_departments = ElementTree.SubElement(self.exclusions,
                                                           "departments")

        # Self Service
        self.self_service = ElementTree.SubElement(self, "self_service")
        self.use_for_self_service = ElementTree.SubElement(
            self.self_service, "use_for_self_service")
        self.set_bool(self.use_for_self_service, True)

        # Package Configuration
        self.pkg_config = ElementTree.SubElement(self, "package_configuration")
        self.pkgs = ElementTree.SubElement(self.pkg_config, "packages")

        # Maintenance
        self.maintenance = ElementTree.SubElement(self, "maintenance")
        self.recon = ElementTree.SubElement(self.maintenance, "recon")
        self.set_bool(self.recon, True)

    def add_object_to_scope(self, obj):
        """Add an object to the appropriate scope block.

        Args:
            obj: JSSObject to add to scope. Accepted subclasses are:
                Computer
                ComputerGroup
                Building
                Department

        Raises:
            TypeError if invalid obj type is provided.
        """
        if isinstance(obj, Computer):
            self.add_object_to_path(obj, "scope/computers")
        elif isinstance(obj, ComputerGroup):
            self.add_object_to_path(obj, "scope/computer_groups")
        elif isinstance(obj, Building):
            self.add_object_to_path(obj, "scope/buildings")
        elif isinstance(obj, Department):
            self.add_object_to_path(obj, "scope/departments")
        else:
            raise TypeError

    def clear_scope(self):
        """Clear all objects from the scope, including exclusions."""
        clear_list = ["computers", "computer_groups", "buildings",
                      "departments", "limit_to_users/user_groups",
                      "limitations/users", "limitations/user_groups",
                      "limitations/network_segments", "exclusions/computers",
                      "exclusions/computer_groups", "exclusions/buildings",
                      "exclusions/departments", "exclusions/users",
                      "exclusions/user_groups", "exclusions/network_segments"]
        for section in clear_list:
            self.clear_list("%s%s" % ("scope/", section))

    def add_object_to_exclusions(self, obj):
        """Add an object to the appropriate scope exclusions
        block.

        Args:
            obj: JSSObject to add to exclusions. Accepted subclasses
                    are:
                Computer
                ComputerGroup
                Building
                Department

        Raises:
            TypeError if invalid obj type is provided.
        """
        if isinstance(obj, Computer):
            self.add_object_to_path(obj, "scope/exclusions/computers")
        elif isinstance(obj, ComputerGroup):
            self.add_object_to_path(obj, "scope/exclusions/computer_groups")
        elif isinstance(obj, Building):
            self.add_object_to_path(obj, "scope/exclusions/buildings")
        elif isinstance(obj, Department):
            self.add_object_to_path(obj, "scope/exclusions/departments")
        else:
            raise TypeError

    def add_package(self, pkg):
        """Add a Package object to the policy with action=install.

        Args:
            pkg: A Package object to add.
        """
        if isinstance(pkg, Package):
            package = self.add_object_to_path(
                pkg, "package_configuration/packages")
            action = ElementTree.SubElement(package, "action")
            action.text = "Install"

    def set_self_service(self, state=True):
        """Set use_for_self_service to bool state."""
        self.set_bool(self.find("self_service/use_for_self_service"), state)

    def set_recon(self, state=True):
        """Set policy's recon value to bool state."""
        self.set_bool(self.find("maintenance/recon"), state)

    def set_category(self, category):
        """Set the policy's category.

        Args:
            category: A category object.
        """
        pcategory = self.find("general/category")
        pcategory.clear()
        name = ElementTree.SubElement(pcategory, "name")
        if isinstance(category, Category):
            id_ = ElementTree.SubElement(pcategory, "id")
            id_.text = category.id
            name.text = category.name
        elif isinstance(category, basestring):
            name.text = category


class Printer(JSSContainerObject):
    _url = "/printers"


class RestrictedSoftware(JSSContainerObject):
    _url = "/restrictedsoftware"


class RemovableMACAddress(JSSContainerObject):
    _url = "/removablemacaddresses"


class SavedSearch(JSSContainerObject):
    _url = "/savedsearches"
    can_put = False
    can_post = False
    can_delete = False


class Script(JSSContainerObject):
    _url = "/scripts"
    list_type = "script"


class Site(JSSContainerObject):
    _url = "/sites"
    list_type = "site"


class SoftwareUpdateServer(JSSContainerObject):
    _url = "/softwareupdateservers"


class SMTPServer(JSSFlatObject):
    _url = "/smtpserver"
    id_url = ""
    can_list = False
    can_post = False
    search_types = {}


class UserExtensionAttribute(JSSContainerObject):
    _url = "/userextensionattributes"


class User(JSSContainerObject):
    _url = "/users"


class UserGroup(JSSContainerObject):
    _url = "/usergroups"


class VPPAccount(JSSContainerObject):
    _url = "/vppaccounts"
    list_type = "vpp_account"

# pylint: enable=missing-docstring
