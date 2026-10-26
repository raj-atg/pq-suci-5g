# Patches

| File | Applies to | What it adds |
|---|---|---|
| `open5gs-v2.8.0-pq-suci.patch` | Open5GS v2.8.0 | SUCI scheme 12 (ML-KEM-768) in the AMF and the UDM/SIDF, ML-KEM hnet keys, SIDF timing log |
| `ueransim-v3.3.0-pq-suci.patch` | UERANSIM v3.3.0 | SUCI Profile B and scheme 12 on the UE, longer home network public keys, SUCI timing log |

Apply and build with `scripts/apply_patches.sh`. Details: [docs/05-tier3-integration.md](../docs/05-tier3-integration.md).

## License

These patches modify Open5GS (AGPL-3.0) and UERANSIM (GPL-3.0). They are derivative works of
those projects and are licensed under the same license as the project they modify, not under
the MIT license in the repository root.
