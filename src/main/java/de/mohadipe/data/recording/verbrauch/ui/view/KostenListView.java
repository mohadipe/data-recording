package de.mohadipe.data.recording.verbrauch.ui.view;

import com.vaadin.flow.component.button.Button;
import com.vaadin.flow.component.button.ButtonVariant;
import com.vaadin.flow.component.datepicker.DatePicker;
import com.vaadin.flow.component.grid.Grid;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.select.Select;
import com.vaadin.flow.component.textfield.NumberField;
import com.vaadin.flow.component.textfield.TextField;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.verbrauch.domain.Kosten;
import de.mohadipe.data.recording.verbrauch.service.KostenService;
import de.mohadipe.data.recording.verbrauch.view.model.KostenEinheit;
import jakarta.annotation.security.PermitAll;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("kosten-list")
@PageTitle("Kosten List")
@Menu(order = 0, icon = "vaadin:cash", title = "Kosten List") // https://yesicon.app/vaadin
@PermitAll // When security is enabled, allow all authenticated users
public class KostenListView extends Main {

    private final KostenService kostenService;

    final TextField ressource;
    final DatePicker von;
    final DatePicker bis;
    final NumberField preis;
    final Select<KostenEinheit> kostenEinheit;
    final Button createBtn;
    final Grid<Kosten> kostenGrid;

    public KostenListView(KostenService kostenService, Clock clock) {
        this.kostenService = kostenService;

        ressource = new TextField();
        ressource.setLabel("Ressourcen Name");
        ressource.setPlaceholder("ressourcen Nummer");
        ressource.setAriaLabel("Ressourcen Name");
        ressource.setMaxLength(Kosten.NUMBER_MAX_LENGTH);
        ressource.setMinWidth("20em");

        von = new DatePicker("Einbau Datum");
        von.setValue(LocalDate.now(clock));
        bis = new DatePicker("Ausbau Datum");
        bis.setValue(LocalDate.now(clock));

        preis = new NumberField("Preis");
        preis.setRequired(true);
        preis.setHelperText("Bitte geben Sie den Preis ein.");

        kostenEinheit = new Select<>();
        kostenEinheit.setItems(KostenEinheit.values());
        kostenEinheit.setLabel("Kosten Einheit");
        kostenEinheit.setValue(KostenEinheit.CT_PRO_KWH);

        createBtn = new Button("Create", event -> createKosten());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        kostenGrid = new Grid<>();
        kostenGrid.setItems(query -> kostenService.list(toSpringPageRequest(query)).stream());
        kostenGrid.addColumn(Kosten::getRessource).setHeader("Ressource");
        kostenGrid.addColumn(Kosten::getVon).setHeader("Von Datum");
        kostenGrid.addColumn(Kosten::getBis).setHeader("Bis Datum");
        kostenGrid.addColumn(Kosten::getPreis).setHeader("Pries");
        kostenGrid.addColumn(Kosten::getEinheit).setHeader("Einheit");
        kostenGrid.setSizeFull();

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);

        add(new ViewToolbar("Kosten List", ViewToolbar.group(ressource, von, bis, preis, kostenEinheit, createBtn)));
        add(kostenGrid);
    }

    private void createKosten() {
        kostenService.createKosten(ressource.getValue(), von.getValue(), bis.getValue(), BigDecimal.valueOf(preis.getValue()), kostenEinheit.getValue().name());
        kostenGrid.getDataProvider().refreshAll();

        ressource.clear();
        preis.setValue(0.0);
        Notification.show("Kosten added", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
