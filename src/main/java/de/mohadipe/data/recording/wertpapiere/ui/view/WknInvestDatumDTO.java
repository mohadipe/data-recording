package de.mohadipe.data.recording.wertpapiere.ui.view;

import de.mohadipe.data.recording.wertpapiere.domain.WknInvestDatum;

import java.math.BigDecimal;
import java.time.LocalDate;

public record WknInvestDatumDTO(String wknNummer, LocalDate datum, BigDecimal invest) {
    public static WknInvestDatumDTO from(WknInvestDatum entity) {
        return new WknInvestDatumDTO(
                entity.getWkn().getWkn(),
                entity.getDatum(),
                entity.getInvest()
        );
    }
}
