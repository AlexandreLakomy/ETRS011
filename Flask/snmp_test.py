from pysnmp.hlapi import *

def check_snmp_device(ip, community):
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),  # SNMPv2c
        UdpTransportTarget((ip, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0'))  # sysDescr
    )

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:
        print(f"[{ip}] Erreur : {errorIndication}")
    elif errorStatus:
        print(f"[{ip}] Erreur : {errorStatus.prettyPrint()}")
    else:
        for varBind in varBinds:
            print(f"[{ip}] OK → {varBind}")

# Test NAS
check_snmp_device("192.168.176.2", "passprojet")

# Test Switch
check_snmp_device("192.168.140.141", "passprojet")
