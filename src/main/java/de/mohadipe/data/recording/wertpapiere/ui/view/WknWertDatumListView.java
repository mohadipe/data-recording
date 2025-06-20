package de.mohadipe.data.recording.wertpapiere.ui.view;

import com.vaadin.flow.component.button.Button;
import com.vaadin.flow.component.button.ButtonVariant;
import com.vaadin.flow.component.datepicker.DatePicker;
import com.vaadin.flow.component.grid.Grid;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.html.Span;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.select.Select;
import com.vaadin.flow.component.textfield.NumberField;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.wertpapiere.domain.Etf;
import de.mohadipe.data.recording.wertpapiere.domain.WknInvestDatum;
import de.mohadipe.data.recording.wertpapiere.domain.WknWertDatum;
import de.mohadipe.data.recording.wertpapiere.service.EtfService;
import de.mohadipe.data.recording.wertpapiere.service.WknInvestDatumService;
import de.mohadipe.data.recording.wertpapiere.service.WknWertDatumService;
import jakarta.annotation.security.PermitAll;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.util.Locale;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("wkn-wert-datum-list")
@PageTitle("Wkn Wert Datum List")
@Menu(order = 0, icon = "vaadin:clipboard-check", title = "Wkn Wert Datum List")
@PermitAll // When security is enabled, allow all authenticated users
public class WknWertDatumListView extends Main {

    private final WknWertDatumService wknWertDatumService;

    final Select<Etf> select;
    final Button createBtn;
    final Grid<WknWertDatumDTO> taskGrid;
    final DatePicker wertDatum;
    final NumberField betrag;

    public WknWertDatumListView(WknWertDatumService wknWertDatumService, EtfService etfService, Clock clock) {
        this.wknWertDatumService = wknWertDatumService;

        select = new Select<>();
        select.setLabel("Wkn");
        select.setItems(etfService.list(Pageable.unpaged())); // Lädt alle ETFs
        select.setItemLabelGenerator(Etf::getWkn);

        // datum
        wertDatum = new DatePicker("Wert Datum");
        wertDatum.setValue(LocalDate.now(clock));
        wertDatum.setRequired(true);
        wertDatum.setLocale(Locale.GERMAN);

        // invest betrag
        betrag = new NumberField("Betrag (€)");
        betrag.setValue(0.0);
        betrag.setMin(0.01);
        betrag.setStep(0.01);
        betrag.setPrefixComponent(new Span("€"));
        betrag.setRequired(true);
        betrag.setHelperText("Bitte geben Sie den Wertbetrag ein (mindestens 0,01 €)");

        createBtn = new Button("Create", event -> createWknInvest());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        taskGrid = new Grid<>();
        taskGrid.setItems(query -> wknWertDatumService.listAsDTO(toSpringPageRequest(query)).stream());
        taskGrid.addColumn(WknWertDatumDTO::wknNummer).setHeader("WKN");
        taskGrid.addColumn(WknWertDatumDTO::datum).setHeader("Datum");
        taskGrid.addColumn(WknWertDatumDTO::wert).setHeader("Wert");
        taskGrid.setSizeFull();

        select.addValueChangeListener(event -> {
            Etf selectedEtf = event.getValue();
            updateGrid(selectedEtf.getId());
        });

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);


        add(new ViewToolbar("Wert for Etf", ViewToolbar.group(select, wertDatum, betrag, createBtn)));

        add(taskGrid);
    }

    private void updateGrid(Long wkn) {
        taskGrid.setItems(query ->
                wknWertDatumService.listByWknAsDTO(wkn, toSpringPageRequest(query)).stream()
        );
    }

    private void createWknInvest() {
        Etf selectedEtf = select.getValue();
        WknWertDatum wknWertDatum = new WknWertDatum();
        wknWertDatum.setWkn(selectedEtf);
        wknWertDatum.setWert(BigDecimal.valueOf(betrag.getValue()));
        wknWertDatum.setDatum(wertDatum.getValue());

        wknWertDatumService.createWknInvest(wknWertDatum);
        updateGrid(selectedEtf.getId());

        betrag.setValue(0.0);
        Notification.show("Wert hinzugefügt", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
