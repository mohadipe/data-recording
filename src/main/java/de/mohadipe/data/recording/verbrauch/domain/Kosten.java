package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.jspecify.annotations.Nullable;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "kosten")
public class Kosten extends AbstractEntity<Long> {
    public static final int NUMBER_MAX_LENGTH = 100;
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @Size(max = 255)
    @NotNull
    @Column(name = "ressource", nullable = false)
    private String ressource;

    @NotNull
    @Column(name = "von", nullable = false)
    private LocalDate von;

    @NotNull
    @Column(name = "bis", nullable = false)
    private LocalDate bis;

    @NotNull
    @Column(name = "preis", nullable = false, precision = 10, scale = 2)
    private BigDecimal preis;

    @Size(max = 255)
    @NotNull
    @Column(name = "einheit", nullable = false)
    private String einheit;

    public void setId(Long id) {
        this.id = id;
    }

    public BigDecimal getPreis() {
        return preis;
    }

    public void setPreis(BigDecimal preis) {
        this.preis = preis;
    }

    public String getEinheit() {
        return einheit;
    }

    public void setEinheit(String einheit) {
        this.einheit = einheit;
    }

    @Override
    public @Nullable Long getId() {
        return id;
    }

    public void setRessource(String ressource) {
        this.ressource = ressource;
    }

    public void setVon(LocalDate von) {
        this.von = von;
    }

    public void setBis(LocalDate bis) {
        this.bis = bis;
    }

    public String getRessource() {
        return this.ressource;
    }

    public LocalDate getVon() {
        return this.von;
    }

    public LocalDate getBis() {
        return this.bis;
    }
}