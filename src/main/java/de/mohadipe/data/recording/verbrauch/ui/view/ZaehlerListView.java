package de.mohadipe.data.recording.verbrauch.ui.view;

import com.vaadin.flow.component.button.Button;
import com.vaadin.flow.component.button.ButtonVariant;
import com.vaadin.flow.component.datepicker.DatePicker;
import com.vaadin.flow.component.grid.Grid;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.select.Select;
import com.vaadin.flow.component.textfield.TextField;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.verbrauch.domain.Zaehler;
import de.mohadipe.data.recording.verbrauch.service.ZaehlerService;
import de.mohadipe.data.recording.verbrauch.view.model.ZaehlerTyp;
import jakarta.annotation.security.PermitAll;

import java.time.Clock;
import java.time.LocalDate;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("zaehler-list")
@PageTitle("Zaehler List")
@Menu(order = 0, icon = "vaadin:timer", title = "Zaehler List")
@PermitAll // When security is enabled, allow all authenticated users
public class ZaehlerListView extends Main {

    private final ZaehlerService zaehlerService;

    final TextField zaehlerNummer;
    final DatePicker einbauDatum;
    final DatePicker ausbauDatum;
    final Select<ZaehlerTyp> zaehlerTyp;
    final Button createBtn;
    final Grid<Zaehler> zaehlerGrid;

    public ZaehlerListView(ZaehlerService zaehlerService, Clock clock) {
        this.zaehlerService = zaehlerService;

        zaehlerNummer = new TextField();
        zaehlerNummer.setLabel("Zaehler Nummer");
        zaehlerNummer.setPlaceholder("Geräte Nummer");
        zaehlerNummer.setAriaLabel("Zaehler Nummer");
        zaehlerNummer.setMaxLength(Zaehler.NUMBER_MAX_LENGTH);
        zaehlerNummer.setMinWidth("20em");

        einbauDatum = new DatePicker("Einbau Datum");
        einbauDatum.setValue(LocalDate.now(clock));
        ausbauDatum = new DatePicker("Ausbau Datum");
        ausbauDatum.setValue(LocalDate.now(clock));
        zaehlerTyp = new Select<>();
        zaehlerTyp.setItems(ZaehlerTyp.values());
        zaehlerTyp.setLabel("Zaehler Typ");
        zaehlerTyp.setValue(ZaehlerTyp.STROM);

        createBtn = new Button("Create", event -> createZaehler());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        zaehlerGrid = new Grid<>();
        zaehlerGrid.setItems(query -> zaehlerService.list(toSpringPageRequest(query)).stream());
        zaehlerGrid.addColumn(Zaehler::getGeraeteNr).setHeader("Geraete Nr").setSortable(true).setSortProperty("geraeteNr");
        zaehlerGrid.addColumn(Zaehler::getEinbauDt).setHeader("Einbau Datum").setSortable(true).setSortProperty("einbauDt");
        zaehlerGrid.addColumn(Zaehler::getAusbauDt).setHeader("Ausbau Datum").setSortable(true).setSortProperty("ausbauDt");
        zaehlerGrid.addColumn(Zaehler::getTyp).setHeader("Typ").setSortable(true).setSortProperty("typ");
        zaehlerGrid.setSizeFull();

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);

        add(new ViewToolbar("Zaehler List", ViewToolbar.group(zaehlerNummer, einbauDatum, ausbauDatum, zaehlerTyp, createBtn)));
        add(zaehlerGrid);
    }

    private void createZaehler() {
        zaehlerService.createZaehler(zaehlerNummer.getValue(), einbauDatum.getValue(), ausbauDatum.getValue(), zaehlerTyp.getValue().name());
        zaehlerGrid.getDataProvider().refreshAll();
        zaehlerNummer.clear();
        Notification.show("Zaehler added", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
