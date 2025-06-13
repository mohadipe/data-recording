package de.mohadipe.data.recording.wertpapiere.domain;

import de.mohadipe.data.recording.base.domain.AbstractEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.Size;
import org.jspecify.annotations.Nullable;

@Entity
@Table(name = "etf")
public class Etf extends AbstractEntity<Long> {

    public static final int DESCRIPTION_MAX_LENGTH = 255;

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @Column(name = "wkn", nullable = false, length = DESCRIPTION_MAX_LENGTH)
    @Size(max = DESCRIPTION_MAX_LENGTH)
    private String wkn;

    @Override
    public @Nullable Long getId() {
        return id;
    }

    public String getWkn() {
        return wkn;
    }

    public void setWkn(String wkn) {
        this.wkn = wkn;
    }
}
