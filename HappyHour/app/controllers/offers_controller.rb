class OffersController < ApplicationController
  def index
    @offers = Offer.all
  end

  def new
    @bar = Bar.find(params[:id])
    @offer = @bar.offers.new
  end


  def create
    @bar = Bar.find(params[:id])
    @offer = @bar.offers.new(params.require(:offer).permit(:item, :description, :price, :image))
    #@offer.bar =
    if @offer.save
      redirect_to user_path(current_user)
    else
      render :new
    end
  end

  def show
    @bar = Bar.find(params[:id])
    @offers = @bar.offers.all
  end

  def edit
    @offer = Offer.find(params[:id])
  end

  def update
    @offer = Offer.find(params[:id])

    if @offer.update_attributes(params.require(:offer).permit(:item, :description, :price, :image))
      redirect_to user_path(current_user)
    else
      render :edit
    end
  end #end update def

  def destroy
    @offer = Offer.find(params[:id])
    @offer.destroy
    redirect_to user_path(current_user)
  end


end
