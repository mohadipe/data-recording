package de.mohadipe.data.recording.verbrauch.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;
import org.springframework.lang.Nullable;

import java.time.LocalDateTime;

@Entity
@Table(name = "arotherm_plus_data")
public class ArothermPlusData extends AbstractEntity<Long> {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @NotNull
    @Column(name = "date_time", nullable = false)
    private LocalDateTime dateTime;

    @Column(name = "consumed_electrical_energy_heating")
    private Double consumedElectricalEnergyHeating;

    @Column(name = "consumed_electrical_energy_domestic_hot_water")
    private Double consumedElectricalEnergyDomesticHotWater;

    @Column(name = "heat_generated_heating")
    private Double heatGeneratedHeating;

    @Column(name = "heat_generated_domestic_hot_water")
    private Double heatGeneratedDomesticHotWater;

    @Column(name = "earned_environment_energy_heating")
    private Double earnedEnvironmentEnergyHeating;

    @Column(name = "earned_environment_energy_domestic_hot_water")
    private Double earnedEnvironmentEnergyDomesticHotWater;

    @Override
    public @Nullable Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public LocalDateTime getDateTime() {
        return dateTime;
    }

    public void setDateTime(LocalDateTime dateTime) {
        this.dateTime = dateTime;
    }

    public Double getConsumedElectricalEnergyHeating() {
        return consumedElectricalEnergyHeating;
    }

    public void setConsumedElectricalEnergyHeating(Double consumedElectricalEnergyHeating) {
        this.consumedElectricalEnergyHeating = consumedElectricalEnergyHeating;
    }

    public Double getConsumedElectricalEnergyDomesticHotWater() {
        return consumedElectricalEnergyDomesticHotWater;
    }

    public void setConsumedElectricalEnergyDomesticHotWater(Double consumedElectricalEnergyDomesticHotWater) {
        this.consumedElectricalEnergyDomesticHotWater = consumedElectricalEnergyDomesticHotWater;
    }

    public Double getHeatGeneratedHeating() {
        return heatGeneratedHeating;
    }

    public void setHeatGeneratedHeating(Double heatGeneratedHeating) {
        this.heatGeneratedHeating = heatGeneratedHeating;
    }

    public Double getHeatGeneratedDomesticHotWater() {
        return heatGeneratedDomesticHotWater;
    }

    public void setHeatGeneratedDomesticHotWater(Double heatGeneratedDomesticHotWater) {
        this.heatGeneratedDomesticHotWater = heatGeneratedDomesticHotWater;
    }

    public Double getEarnedEnvironmentEnergyHeating() {
        return earnedEnvironmentEnergyHeating;
    }

    public void setEarnedEnvironmentEnergyHeating(Double earnedEnvironmentEnergyHeating) {
        this.earnedEnvironmentEnergyHeating = earnedEnvironmentEnergyHeating;
    }

    public Double getEarnedEnvironmentEnergyDomesticHotWater() {
        return earnedEnvironmentEnergyDomesticHotWater;
    }

    public void setEarnedEnvironmentEnergyDomesticHotWater(Double earnedEnvironmentEnergyDomesticHotWater) {
        this.earnedEnvironmentEnergyDomesticHotWater = earnedEnvironmentEnergyDomesticHotWater;
    }
}
