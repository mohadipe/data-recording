package de.mohadipe.data.recording.wertpapiere.domain;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "wkn_wert_datum")
public class WknWertDatum {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Integer id;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "wkn_id", nullable = false)
    private Etf wkn;

    @NotNull
    @Column(name = "datum", nullable = false)
    private LocalDate datum;

    @NotNull
    @Column(name = "wert", nullable = false, precision = 10, scale = 2)
    private BigDecimal wert;

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public Etf getWkn() {
        return wkn;
    }

    public void setWkn(Etf wkn) {
        this.wkn = wkn;
    }

    public LocalDate getDatum() {
        return datum;
    }

    public void setDatum(LocalDate datum) {
        this.datum = datum;
    }

    public BigDecimal getWert() {
        return wert;
    }

    public void setWert(BigDecimal wert) {
        this.wert = wert;
    }

}