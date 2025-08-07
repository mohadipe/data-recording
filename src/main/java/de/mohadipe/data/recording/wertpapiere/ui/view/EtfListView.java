package de.mohadipe.data.recording.wertpapiere.ui.view;

import com.vaadin.flow.component.button.Button;
import com.vaadin.flow.component.button.ButtonVariant;
import com.vaadin.flow.component.grid.Grid;
import com.vaadin.flow.component.html.Main;
import com.vaadin.flow.component.notification.Notification;
import com.vaadin.flow.component.notification.NotificationVariant;
import com.vaadin.flow.component.textfield.TextField;
import com.vaadin.flow.router.Menu;
import com.vaadin.flow.router.PageTitle;
import com.vaadin.flow.router.Route;
import com.vaadin.flow.theme.lumo.LumoUtility;
import de.mohadipe.data.recording.base.ui.component.ViewToolbar;
import de.mohadipe.data.recording.wertpapiere.domain.Etf;
import de.mohadipe.data.recording.wertpapiere.service.EtfService;
import jakarta.annotation.security.PermitAll;

import java.time.Clock;

import static com.vaadin.flow.spring.data.VaadinSpringDataHelpers.toSpringPageRequest;

@Route("etf-list")
@PageTitle("Etf List")
@Menu(order = 0, icon = "vaadin:file-text-o", title = "Etf List")
@PermitAll // When security is enabled, allow all authenticated users
public class EtfListView extends Main {

    private final EtfService etfService;

    final TextField wkn;
    final Button createBtn;
    final Grid<Etf> taskGrid;

    public EtfListView(EtfService etfService, Clock clock) {
        this.etfService = etfService;

        wkn = new TextField();
        wkn.setPlaceholder("What do you want to do?");
        wkn.setAriaLabel("Etf WKN");
        wkn.setMaxLength(Etf.DESCRIPTION_MAX_LENGTH);
        wkn.setMinWidth("20em");

        createBtn = new Button("Create", event -> createEtf());
        createBtn.addThemeVariants(ButtonVariant.LUMO_PRIMARY);

        taskGrid = new Grid<>();
        taskGrid.setItems(query -> etfService.list(toSpringPageRequest(query)).stream());
        taskGrid.addColumn(Etf::getWkn).setHeader("Wkn");
        taskGrid.setSizeFull();

        setSizeFull();
        addClassNames(LumoUtility.BoxSizing.BORDER, LumoUtility.Display.FLEX, LumoUtility.FlexDirection.COLUMN,
                LumoUtility.Padding.MEDIUM, LumoUtility.Gap.SMALL);

        add(new ViewToolbar("Etf List", ViewToolbar.group(wkn, createBtn)));
        add(taskGrid);
    }

    private void createEtf() {
        etfService.createEtf(wkn.getValue());
        taskGrid.getDataProvider().refreshAll();
        wkn.clear();
        Notification.show("Etf added", 3000, Notification.Position.BOTTOM_END)
                .addThemeVariants(NotificationVariant.LUMO_SUCCESS);
    }

}
