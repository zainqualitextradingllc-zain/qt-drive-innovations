"use client";

import { useTranslations } from "next-intl";
import type { VehicleContext } from "@/types/diagnosis";

export function VehicleChip({ vehicle }: { vehicle: VehicleContext | null | undefined }) {
  const t = useTranslations("vehicle");

  if (!vehicle || (!vehicle.make && !vehicle.model && !vehicle.vin)) {
    return null;
  }

  const title = [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ");

  return (
    <div className="vehicle-chip" aria-label={t("label")}>
      <strong>{t("label")}:</strong>
      <span>{title || t("unknown")}</span>
      {vehicle.engine ? <span className="muted">{vehicle.engine}</span> : null}
      {vehicle.vin ? (
        <span className="muted">
          {t("vin")} {vehicle.vin}
        </span>
      ) : null}
    </div>
  );
}
