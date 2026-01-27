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
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.verbrauch.domain.Messwerte;
import de.mohadipe.data.recording.verbrauch.domain.Zaehler;
import de.mohadipe.data.recording.verbrauch.service.MesswerteService;
import de.mohadipe.data.recording.verbrauch.service.ZaehlerService;
import de.mohadipe.data.recording.verbrauch.view.model.MesswertDto;
import de.mohadipe.data.recording.verbrauch.view.model.MesswertEinheit;
import jakarta.annotation.security.PermitAll;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.Locale;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("messwerte-list")
@PageTitle("Messwerte List")
@Menu(order = 0, icon = "vaadin:line-bar-chart", title = "Messwerte List")
@PermitAll // When security is enabled, allow all authenticated users
public class MesswerteListView extends Main {

    private final MesswerteService messwerteService;

    final Select<Zaehler> select;
    final Button createBtn;
    final Grid<MesswertDto> taskGrid;
    final DatePicker wertDatum;
    final NumberField betrag;
    final Select<MesswertEinheit> messEinheit;

    public MesswerteListView(MesswerteService messwerteService, ZaehlerService zaehlerService, Clock clock) {
        this.messwerteService = messwerteService;

        select = new Select<>();
        select.setLabel("Zaehler Nummer");
        List<Zaehler> zaehlerList = zaehlerService.list(Pageable.unpaged());
        select.setItems(zaehlerList);
        select.setItemLabelGenerator(Zaehler::getGeraeteNr);

        // datum
        wertDatum = new DatePicker("Messwert Datum");
        wertDatum.setValue(LocalDate.now(clock));
        wertDatum.setRequired(true);
        wertDatum.setLocale(Locale.GERMAN);

        betrag = new NumberField("Messwert");
        betrag.setRequired(true);
        betrag.setHelperText("Bitte geben Sie den Messwert ein.");

        messEinheit = new Select<>();
        messEinheit.setLabel("Messwert Einheit");
        messEinheit.setItems(MesswertEinheit.values());
        messEinheit.setValue(MesswertEinheit.KWH);

        createBtn = new Button("Create", event -> createMesswert());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        taskGrid = new Grid<>();
        taskGrid.setItems(query -> messwerteService.listAsDTO(toSpringPageRequest(query)).stream());
        taskGrid.addColumn(MesswertDto::geraeteNummer).setHeader("GeräteNummer").setSortable(true).setSortProperty("zaehler.geraeteNr");
        taskGrid.addColumn(MesswertDto::datum).setHeader("Datum").setSortable(true).setSortProperty("datum");
        taskGrid.addColumn(MesswertDto::wert).setHeader("Wert").setSortable(true).setSortProperty("wert");
        taskGrid.addColumn(MesswertDto::einheit).setHeader("Einheit").setSortable(true).setSortProperty("einheit");
        taskGrid.setSizeFull();

        select.addValueChangeListener(event -> {
            Zaehler selectedZaehler = event.getValue();
            if (selectedZaehler != null) {
                updateGrid(selectedZaehler.getId());
            }
        });

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);


        add(new ViewToolbar("Wert for Zaehler", ViewToolbar.group(select, wertDatum, betrag, messEinheit, createBtn)));

        add(taskGrid);

        if (!zaehlerList.isEmpty()) {
            select.setValue(zaehlerList.get(0));
        } else {
            Notification.show("Es wurden noch keine Zähler angelegt.", 5000, Notification.Position.MIDDLE)
                    .addThemeVariants(NotificationVariant.LUMO_WARNING);
        }
    }

    private void updateGrid(Long zaehlerId) {
        taskGrid.setItems(query ->
                messwerteService.listByZaehlerAsDTO(zaehlerId, toSpringPageRequest(query)).stream()
        );
    }

    private void createMesswert() {
        Zaehler selectedZaehler = select.getValue();
        if (selectedZaehler == null) {
            Notification.show("Bitte wählen Sie zuerst einen Zähler aus.", 3000, Notification.Position.MIDDLE)
                    .addThemeVariants(NotificationVariant.LUMO_ERROR);
            return;
        }
        Messwerte messwerte = new Messwerte();
        messwerte.setZaehler(selectedZaehler);
        messwerte.setWert(BigDecimal.valueOf(betrag.getValue()));
        messwerte.setDatum(wertDatum.getValue());
        messwerte.setEinheit(messEinheit.getValue().name());

        messwerteService.createMesswert(messwerte);
        updateGrid(selectedZaehler.getId());

        betrag.setValue(0.0);
        Notification.show("Wert hinzugefügt", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
