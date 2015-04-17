class BarsController < ApplicationController
  def index
    @bars = Bar.all
  end

  def new
    @bar = Bar.new
  end


  def create

    @bar = Bar.new(params.require(:bar).permit(:bar_name, :location, :zip, :day))
    @bar.user = current_user
    if @bar.save
      redirect_to user_path(current_user)
    else
      render :new
    end
  end

  def show
    
  end

  def edit
    @bar = Bar.find(params[:id])
  end

  def update
    @bar = Bar.find(params[:id])

    if @bar.update_attributes(params.require(:bar).permit(:bar_name, :location, :zip, :day))
      redirect_to user_path(current_user)
    else
      render :edit
    end
  end #end update def

  def destroy
    @bar = Bar.find(params[:id])
    @bar.destroy
    redirect_to user_path(current_user)
  end


end
